"""Build censitário offline, com lock, qualidade e rollback de promoção."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pandas as pd

from pipelines.cli._promote import promote_paths
from pipelines.collectors.censos2021.coverage import write_censos_reports
from pipelines.collectors.censos2021.prepare import (
    dependency_hashes,
    prepare_censos,
    sha256_file,
)

TABLES = {
    "census_age_category": "bronze",
    "census_observation": "bronze",
    "census_parish_observation": "silver",
    "census_coverage": "silver",
}
PROMOTED = tuple(f"lake/{layer}/{table}" for table, layer in TABLES.items()) + (
    "lake/silver/census_reports",
)


def _run_dbt(candidate, silver):
    executable = shutil.which("dbt")
    if not executable:
        raise ValueError("dbt não encontrado; execute com uv run --locked")
    env = {
        **os.environ,
        "CENSOS_BUILD_DIR": candidate.as_posix(),
        "CENSOS_PREPARED_DIR": (candidate / "prepared").as_posix(),
        "OBS_SILVER_DIR": silver.as_posix(),
        "CAOP_DUCKDB_PATH": (candidate / "censos.duckdb").as_posix(),
    }
    command = [
        executable,
        "build",
        "--project-dir",
        "analytics/dbt",
        "--profiles-dir",
        "analytics/dbt",
        "--target",
        "local",
        "--select",
        "tag:censos",
        "--target-path",
        str(candidate / "dbt-target"),
        "--log-path",
        str(candidate / "dbt-logs"),
    ]
    result = subprocess.run(
        command,
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ValueError(
            "dbt censos falhou:\n"
            + "\n".join((result.stdout + result.stderr).splitlines()[-30:])
        )


def _verify_exports(candidate):
    for table, layer in TABLES.items():
        exported = candidate / f"lake/{layer}/{table}/data.parquet"
        expected = candidate / f"prepared/{table}.parquet"
        if not exported.is_file():
            raise ValueError(f"saída ausente: {table}")
        first, second = pd.read_parquet(expected), pd.read_parquet(exported)
        pd.testing.assert_frame_equal(first, second, check_dtype=False)
    for name in ("coverage.csv", "summary.csv", "readiness.json", "orphans.csv"):
        if not (candidate / "lake/silver/census_reports" / name).is_file():
            raise ValueError(f"relatório ausente: {name}")


def verify_destination_paths(root):
    root = Path(root).resolve()
    for relative in (
        *PROMOTED,
        ".build/censos",
        "reports/censos",
        "lake/silver/dim_parish",
        "lake/silver/dim_municipality",
        "lake/silver/xwalk_parish_2013_2025",
    ):
        if not (root / relative).resolve().is_relative_to(root):
            raise ValueError(f"caminho resolvido fora da raiz: {relative}")


def output_hashes(base):
    return {
        str(file.relative_to(base)): sha256_file(file)
        for relative in PROMOTED
        for file in (base / relative).rglob("*")
        if file.is_file()
    }


def build_censos(root: Path = Path(".data"), *, run_id=None, dbt_runner=None):
    root = Path(root).resolve()
    verify_destination_paths(root)
    parent = root / ".build/censos"
    parent.mkdir(parents=True, exist_ok=True)
    if not parent.resolve().is_relative_to(root):
        raise ValueError("diretório candidato fora da raiz")
    lock = parent / "build.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ValueError(
            f"build censitário ocupado/interrompido: {lock}; revisar recuperação"
        ) from exc
    build_id = uuid4().hex
    candidate = (parent / build_id).resolve()
    warnings = []
    try:
        os.write(fd, json.dumps({"pid": os.getpid(), "build_id": build_id}).encode())
        os.close(fd)
        fd = None
        candidate.mkdir()
        summary = prepare_censos(root, candidate, run_id=run_id)
        result = write_censos_reports(summary, candidate)
        result["maintenance_warnings"] = warnings
        if not result["ready"]:
            raise ValueError(f"prontidão reprovada: {result['blockers']}")
        (dbt_runner or _run_dbt)(candidate, root / "lake/silver")
        _verify_exports(candidate)
        if dependency_hashes(root) != summary["dependency_hashes"]:
            raise ValueError("dependência territorial mudou durante build")
        results = candidate / "dbt-target/run_results.json"
        if results.is_file():
            shutil.copyfile(
                results, candidate / "lake/silver/census_reports/dbt_run_results.json"
            )
        verify_destination_paths(root)
        expected_hashes = output_hashes(candidate)
        try:
            promote_paths(root, candidate, PROMOTED)
        except OSError as exc:
            # Cleanup in the shared helper happens after every move. A completed promotion
            # is acknowledged only if all staged paths moved and all output bytes match.
            if (
                any((candidate / p).exists() for p in PROMOTED)
                or output_hashes(root) != expected_hashes
            ):
                raise
            warnings.append(
                f"Versão promovida e verificada; limpeza de backups pendente: {exc}"
            )
        return result
    except Exception as exc:
        diagnostics = root / "reports/censos" / build_id
        diagnostics.mkdir(parents=True, exist_ok=True)
        (diagnostics / "failure.json").write_text(
            json.dumps({"build_id": build_id, "error": str(exc)}, ensure_ascii=False),
            encoding="utf8",
        )
        if (candidate / "dbt-logs").is_dir():
            shutil.copytree(candidate / "dbt-logs", diagnostics / "dbt-logs")
        raise
    finally:
        if fd is not None:
            os.close(fd)
        # Only our confined candidate; do not recursively remove a substituted symlink.
        if (
            candidate.is_dir()
            and not candidate.is_symlink()
            and candidate.resolve().is_relative_to(parent.resolve())
        ):
            try:
                shutil.rmtree(candidate)
            except OSError as exc:
                warnings.append(f"Limpeza do candidato pendente: {exc}")
        try:
            lock.unlink(missing_ok=True)
        except OSError as exc:
            warnings.append(f"Limpeza do lock próprio pendente: {exc}")
        if warnings:
            for warning in warnings:
                print(f"Censos: manutenção: {warning}", file=sys.stderr)
            try:
                report = root / "reports/censos" / build_id
                report.mkdir(parents=True, exist_ok=True)
                (report / "maintenance.json").write_text(
                    json.dumps(warnings, ensure_ascii=False), encoding="utf8"
                )
            except OSError:
                pass  # Maintenance after a verified commit does not invalidate that version.


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Prepara e valida Censos 2021 sem nova coleta."
    )
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--root", type=Path, default=Path(".data"))
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    try:
        result = build_censos(args.root, run_id=args.run_id)
    except (ValueError, OSError, KeyError, AssertionError) as exc:
        print(f"Censos: falha: {exc}", file=sys.stderr)
        return 1
    print(
        f"Censos: edição 2021 | CAOP {result['caop_version']} | run={result['run_id']} | {result['parishes']} freguesias | {result['counts']}"
    )
    print(f"Relatórios: {args.root / 'lake/silver/census_reports'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
