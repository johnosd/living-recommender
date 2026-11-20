"""Build Wikipedia offline com candidato isolado e promoção recuperável."""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

import pandas as pd

from pipelines.cli._common import new_run_id
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors.wikipedia.local import (
    confined,
    dependency_hashes,
    file_hash,
    source_lock,
)
from pipelines.collectors.wikipedia.manifest import (
    digest,
    encode,
    read_manifests,
    validate_run_id,
)
from pipelines.collectors.wikipedia.prepare import TABLES, prepare_wikipedia
from pipelines.collectors.wikipedia.promotion import (
    PROMOTED,
    atomic_json,
    promote,
    recover,
)

REPORT_FILES = {"coverage.csv", "sections.csv", "readiness.json", "summary.json", "dbt_run_results.json"}


def run_dbt(candidate, silver):
    for table, layer in TABLES.items():
        (candidate / f"lake/{layer}/{table}").mkdir(parents=True, exist_ok=True)
    executable = shutil.which("dbt")
    if not executable:
        raise ValueError("dbt não encontrado; execute com uv run --locked")
    env = {**os.environ, "WIKIPEDIA_BUILD_DIR": candidate.as_posix(),
        "WIKIPEDIA_PREPARED_DIR": (candidate / "prepared").as_posix(), "OBS_SILVER_DIR": silver.as_posix(),
        "CAOP_DUCKDB_PATH": (candidate / "wikipedia.duckdb").as_posix(),
        "DBT_TARGET_PATH": (candidate / "dbt-target").as_posix(), "DBT_LOG_PATH": (candidate / "dbt-logs").as_posix()}
    command = [executable, "build", "--project-dir", "analytics/dbt", "--profiles-dir", "analytics/dbt",
               "--target", "local", "--select", "tag:wikipedia"]
    result = subprocess.run(command, cwd=Path(__file__).resolve().parents[2], env=env,
                            capture_output=True, text=True, check=False)
    (candidate / "dbt-output.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise ValueError("dbt Wikipedia falhou: " + "\n".join((result.stdout + result.stderr).splitlines()[-25:]))


def verify_exports(candidate):
    for table, layer in TABLES.items():
        expected = pd.read_parquet(candidate / f"prepared/{table}.parquet")
        exported = pd.read_parquet(candidate / f"lake/{layer}/{table}/data.parquet")
        pd.testing.assert_frame_equal(expected, exported, check_dtype=False)
    result = json.loads((candidate / "dbt-target/run_results.json").read_bytes())
    if not result["results"] or any(row["status"] not in {"success", "pass"} for row in result["results"]):
        raise ValueError("resultados dbt incompletos/reprovados")
    expected_models = {f"model.caop_territory.{table}" for table in TABLES}
    if not expected_models <= {r["unique_id"] for r in result["results"]}:
        raise ValueError("dbt não executou os cinco modelos")
    return result


def integrity_paths():
    return {f"lake/{layer}/{table}/data.parquet" for table, layer in TABLES.items()} | {
        f"lake/silver/wikipedia_reports/{name}" for name in REPORT_FILES}


def write_integrity(candidate):
    hashes = {relative: file_hash(confined(candidate, relative)) for relative in sorted(integrity_paths())}
    atomic_json(candidate / "lake/silver/wikipedia_reports/integrity.json", hashes)


def verify_current(root):
    receipt = confined(root, "lake/silver/wikipedia_reports/integrity.json")
    if not receipt.exists():
        if any(confined(root, path).exists() for path in PROMOTED):
            raise ValueError("lake Wikipedia existente sem recibo de integridade")
        return None
    hashes = json.loads(receipt.read_bytes())
    if set(hashes) != integrity_paths() or any(file_hash(confined(root, p)) != h for p, h in hashes.items()):
        raise ValueError("lake vigente corrompido; não tratar como unchanged")
    summary = json.loads(confined(root, "lake/silver/wikipedia_reports/summary.json").read_bytes())
    return summary["processing_signature"]


def build(root, *, run_id=None, dbt_runner=run_dbt):
    root = Path(root).resolve()
    build_id = new_run_id()
    receipt = confined(root, f"reports/wikipedia/build/{build_id}/summary.json")
    result = {"status": "failed", "build_id": build_id, "error": None}
    try:
        with source_lock(root):
            for relative in (*PROMOTED, ".build/wikipedia", "manifests/wikipedia", "lake/silver/dim_municipality"):
                confined(root, relative)
            recovery = recover(root)
            storage = LocalStorage(root)
            manifests = read_manifests(storage)
            if not manifests:
                raise ValueError("nenhuma tentativa Wikipedia")
            latest = manifests[-1]
            selected = next((m for m in manifests if m["run_id"] == run_id), None) if run_id else latest
            if selected is None:
                raise ValueError("run solicitado não existe")
            result.update(selected_run_id=selected["run_id"], latest_run_id=latest["run_id"],
                          latest_status=latest["status"], selected_older=selected["run_id"] != latest["run_id"], recovery=recovery)
            candidate = confined(root, f".build/wikipedia/{build_id}")
            candidate.mkdir(parents=True, exist_ok=False)
            manifest_path = storage.local_path(f"manifests/wikipedia/{validate_run_id(selected['run_id'])}.json")
            selected_bytes = manifest_path.read_bytes()
            selected = json.loads(selected_bytes)
            initial = {str(manifest_path.resolve()): digest(selected_bytes)}
            prepared = prepare_wikipedia(storage, selected, candidate, root / "lake/silver/dim_municipality/data.parquet")
            reports = candidate / "lake/silver/wikipedia_reports"
            result.update(readiness=prepared["readiness"], processing_signature=prepared["processing_signature"],
                          counts=prepared["counts"], candidate=candidate.relative_to(root).as_posix())
            receipt.parent.mkdir(parents=True, exist_ok=True)
            for name in ("coverage.csv", "sections.csv", "readiness.json"):
                shutil.copyfile(reports / name, receipt.parent / name)
            if not prepared["readiness"]["ready"]:
                raise ValueError("prontidão reprovada: " + "; ".join(prepared["readiness"]["blockers"]))
            dependencies = {**initial, **prepared["dependencies"]}
            check = lambda: dependency_hashes(dependencies) == dependencies
            dbt_runner(candidate, root / "lake/silver")
            dbt_results = verify_exports(candidate)
            (reports / "dbt_run_results.json").write_bytes(encode(dbt_results))
            if not check():
                raise ValueError("dependências alteradas após dbt")
            current_signature = verify_current(root)
            write_integrity(candidate)
            if current_signature == prepared["processing_signature"]:
                result["status"] = "unchanged"
            else:
                result["maintenance_warning"] = promote(root, candidate, check_dependencies=check)
                result["status"] = "promoted"
    except (ValueError, OSError, KeyError, AssertionError, KeyboardInterrupt) as error:
        result["error"] = str(error) or "build interrompido; journal será inspecionado na retomada"
    atomic_json(receipt, result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--root", type=Path, default=Path(".data"))
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    try:
        result = build(args.root, run_id=args.run_id)
    except (ValueError, OSError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] in {"promoted", "unchanged"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
