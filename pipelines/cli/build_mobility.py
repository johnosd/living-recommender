"""Constrói o staging Bronze da mobilidade em isolamento e promove só os caminhos desta fonte (spec 009)."""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pyarrow as pa

from pipelines.cli._common import utc_now
from pipelines.cli._promote import promote_paths
from pipelines.collectors._shared.catalog import load_catalog
from pipelines.collectors._shared.dataset_manifest import latest_dataset_states
from pipelines.collectors._shared.storage import LocalStorage, _canonical_path
from pipelines.collectors.mobility.catalog import SOURCE_ID, mobility_source
from pipelines.collectors.mobility.municipalities import load_mobility_municipalities
from pipelines.collectors.mobility.poles import load_poles
from pipelines.collectors.mobility.rows import build_distance_rows

ROOT = Path(__file__).resolve().parents[2]
BRONZE_TABLES = ("stg_municipality_pole_distance", "dim_mobility_pole", "rpt_mobility_coverage")
PROMOTED = tuple("lake/bronze/" + name for name in BRONZE_TABLES)
REPORTS = ("mobility_coverage.csv", "mobility_no_route.csv", "mobility_pending.csv", "mobility_stale.csv")
STRING_COLUMNS = ("dico", "pole_id", "mode", "status", "no_route_reason", "error", "method", "departure_time",
                  "calculated_at_utc", "source_run_id", "caop_version", "poles_catalog_version", "license_id",
                  "attribution", "usage_restriction", "reference_period", "processed_at_utc")
DISTANCES = pa.schema([*[(name, pa.string()) for name in STRING_COLUMNS[:3]], ("km", pa.float64()),
                       ("minutes", pa.float64()), *[(name, pa.string()) for name in STRING_COLUMNS[3:]],
                       ("stale", pa.bool_())])
POLES = pa.schema([(name, pa.string()) for name in ("pole_id", "name", "kind", "routing_group", "scope", "dico")]
                  + [("latitude", pa.float64()), ("longitude", pa.float64())]
                  + [(name, pa.string()) for name in ("district_or_island", "source_ref")])


class MobilityBuildError(Exception):
    """O candidato não passou nas verificações; a versão anterior é preservada."""


def _write_parquet(path: Path, records: list[dict], schema: pa.Schema) -> None:
    import pyarrow.parquet as pq

    pq.write_table(pa.Table.from_pylist(records, schema=schema), path)


def prepare_mobility(root: Path, output_dir: Path, *, processed_at_utc: str, catalog=None, poles_path=None) -> dict:
    root, output_dir = Path(root).resolve(), Path(output_dir)
    catalog = catalog if catalog is not None else load_catalog()
    source = mobility_source(catalog)
    towns = load_mobility_municipalities(root / "lake/silver")
    poles = load_poles(Path(poles_path) if poles_path else ROOT / "config/poles.yml", towns)
    storage = LocalStorage(root)
    codes, pole_ids = {town["dico"] for town in towns}, {pole["pole_id"] for pole in poles}
    states = latest_dataset_states(storage, SOURCE_ID)
    unknown = sorted({key.split("--")[0] for key in states} - codes)
    if unknown:
        raise MobilityBuildError(f"município sem correspondência na dimensão CAOP: {', '.join(unknown)}")
    retired = sorted(key for key in states if key.split("--")[1] not in pole_ids)
    rows = build_distance_rows(catalog, municipalities=towns, poles=poles, storage=storage,
                               processed_at_utc=processed_at_utc)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_parquet(output_dir / "distances.parquet", rows, DISTANCES)
    _write_parquet(output_dir / "poles.parquet", [{k: pole.get(k) for k in POLES.names} for pole in poles], POLES)
    return {"rows": len(rows), "municipalities": len(towns), "poles": len(poles), "modes": list(source["modes"]),
            "retired_pairs": retired, "towns": towns, "pole_list": poles}


def write_reports(candidate: Path, towns: list[dict], poles: list[dict], modes) -> dict:
    """CSVs de auditoria (`;`, UTF-8 com BOM, como o clima): cobertura, sem rota, pendentes e desatualizados."""
    base = Path(candidate) / "lake/bronze"
    distances = pd.read_parquet(base / "stg_municipality_pole_distance/data.parquet")
    coverage = pd.read_parquet(base / "rpt_mobility_coverage/data.parquet").sort_values(["mode", "pole_id"])
    names = {town["dico"]: town["name"] for town in towns}
    routed = distances[distances["mode"] != "straight_line"]
    no_route = routed[routed["status"] == "sem_rota"].assign(expected_absence=False)
    no_route = no_route.assign(reason=no_route["no_route_reason"])[["dico", "pole_id", "mode", "reason", "expected_absence"]]
    covered = set(routed["dico"])
    # Município sem nenhum polo elegível (ilha sem polo): ausência esperada, não falha da fonte.
    uncovered = [{"dico": town["dico"], "pole_id": "", "mode": mode, "reason": "sem_polo_elegivel",
                  "expected_absence": True}
                 for town in towns if town["dico"] not in covered for mode in modes]
    report = pd.concat([no_route, pd.DataFrame(uncovered, columns=no_route.columns)], ignore_index=True)
    report.insert(1, "name", report["dico"].map(names))
    pending = routed[routed["status"].isin(["pendente", "falha"])][["dico", "pole_id", "mode", "status", "error"]]
    pending = pending.assign(name=pending["dico"].map(names))
    stale = routed[routed["stale"]][["dico", "pole_id", "mode", "status", "calculated_at_utc"]]
    stale = stale.assign(name=stale["dico"].map(names))
    for name, frame in (("mobility_coverage.csv", coverage), ("mobility_no_route.csv", report),
                        ("mobility_pending.csv", pending), ("mobility_stale.csv", stale)):
        frame.to_csv(base / name, sep=";", index=False, encoding="utf-8-sig")
    return {"coverage": coverage, "no_route": report, "pending": pending, "stale": stale}


def format_coverage(coverage: pd.DataFrame) -> str:
    lines = ["Cobertura por modo e polo (ok / sem_rota / falha / pendente de esperados; desatualizados):"]
    for row in coverage.itertuples():
        lines.append(f"  {row.mode:<13} {row.pole_id:<16} {row.ok}/{row.expected}  sem_rota {row.sem_rota}  "
                     f"falha {row.falha}  pendente {row.pendente}  desatualizados {row.stale}")
    return "\n".join(lines)


def _run_dbt(candidate: Path, silver: Path) -> None:
    executable = shutil.which("dbt")
    if executable is None:
        raise MobilityBuildError("dbt não encontrado; execute pelo ambiente uv do projeto")
    env = os.environ.copy()
    env.update({"MOBILITY_BUILD_DIR": candidate.as_posix(), "MOBILITY_PREPARED_DIR": (candidate / "prepared").as_posix(),
                "OBS_SILVER_DIR": silver.as_posix(), "CAOP_DUCKDB_PATH": (candidate / "mobility.duckdb").as_posix()})
    command = [executable, "build", "--project-dir", "analytics/dbt", "--profiles-dir", "analytics/dbt",
               "--target", "local", "--select", "tag:mobility"]
    result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, check=False)
    if result.returncode:
        detail = "\n".join((result.stdout + "\n" + result.stderr).splitlines()[-25:])
        raise MobilityBuildError(f"dbt build falhou (código {result.returncode}):\n{detail}")


def _promote_reports(root: Path, candidate: Path) -> None:
    """CSVs e tabelas voltam juntos à versão anterior se qualquer renomeação falhar."""
    changed = []
    try:
        for name in REPORTS:
            staged, current = candidate / "lake/bronze" / name, root / "lake/bronze" / name
            backup = current.with_name(f".previous-{name}-{candidate.name}")
            current.parent.mkdir(parents=True, exist_ok=True)
            existed = current.exists()
            if existed:
                os.replace(current, backup)
            try:
                os.replace(staged, current)
            except OSError:
                if existed:
                    os.replace(backup, current)
                raise
            changed.append((current, staged, backup, existed))
        promote_paths(root, candidate, PROMOTED)
    except OSError:
        for current, staged, backup, existed in reversed(changed):
            os.replace(current, staged)
            if existed:
                os.replace(backup, current)
        raise
    for _, _, backup, existed in changed:
        if existed:
            backup.unlink()


def build_mobility(root=Path(".data"), *, catalog=None, poles_path=None) -> dict:
    root = Path(root).resolve()
    silver = root / "lake/silver"
    parent = root / ".build/mobility"
    parent.mkdir(parents=True, exist_ok=True)
    candidate = parent / uuid4().hex
    if not _canonical_path(candidate).is_relative_to(_canonical_path(parent)):
        raise MobilityBuildError("diretório temporário fora da raiz autorizada")
    candidate.mkdir()
    try:
        counts = prepare_mobility(root, candidate / "prepared", processed_at_utc=utc_now(), catalog=catalog,
                                  poles_path=poles_path)
        for relative in PROMOTED:
            (candidate / relative).mkdir(parents=True, exist_ok=True)
        _run_dbt(candidate, silver)
        reports = write_reports(candidate, counts["towns"], counts["pole_list"], counts["modes"])
        _promote_reports(root, candidate)
        return {**counts, **reports}
    finally:
        if candidate.exists():
            shutil.rmtree(candidate)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Constrói o staging Bronze da mobilidade (linha reta e carro).")
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--root", type=Path, default=Path(".data"))
    parser.add_argument("--catalog", type=Path, help="catálogo alternativo explícito, inclusive para fixtures")
    parser.add_argument("--poles", type=Path, help="config/poles.yml alternativo, inclusive para fixtures")
    args = parser.parse_args(argv)
    try:
        result = build_mobility(args.root, catalog=load_catalog(args.catalog) if args.catalog else None,
                                poles_path=args.poles)
    except (MobilityBuildError, OSError, ValueError, KeyError) as exc:
        print(f"Mobilidade: falha: {exc}", file=sys.stderr)
        return 1
    print(f"Mobilidade: {result['rows']} linhas de {result['municipalities']} municípios e {result['poles']} polos "
          f"(modos: linha reta, {', '.join(result['modes'])})")
    print(f"  Bronze: {args.root / 'lake/bronze/stg_municipality_pole_distance'}")
    print(format_coverage(result["coverage"]))
    if result["retired_pairs"]:
        print(f"  Pares de polos retirados do catálogo (fora do staging): {len(result['retired_pairs'])}")
    print(f"  Detalhe: {args.root / 'lake/bronze'}/mobility_*.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
