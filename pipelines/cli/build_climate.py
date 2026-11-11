"""Constrói o staging climático em isolamento e promove só os caminhos desta fonte."""
import argparse
import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from pipelines.cli._common import utc_now
from pipelines.cli._promote import promote_paths
from pipelines.collectors._shared.catalog import get_climate_source, load_catalog
from pipelines.collectors._shared.dataset_manifest import latest_dataset_states
from pipelines.collectors._shared.manifest import file_digest
from pipelines.collectors._shared.storage import LocalStorage, _canonical_path
from pipelines.collectors.open_meteo.handler import is_current_state
from pipelines.collectors.open_meteo.municipalities import (
    check_municipalities,
    load_climate_municipalities,
)
from pipelines.collectors.open_meteo.transform import read_climate_response

PROMOTED = tuple("lake/bronze/" + name for name in
                 ("stg_climate_daily", "rpt_climate_coverage", "rpt_climate_points"))
SCHEMA = pa.schema([(name, kind) for name, kind in [
    ("source_id", pa.string()), ("dico", pa.string()), ("variable", pa.string()),
    ("date", pa.date32()), ("value", pa.float64()), ("unit", pa.string()), ("model", pa.string()),
    ("window_start", pa.date32()), ("window_end", pa.date32()), ("source_run_id", pa.string()),
    ("license_id", pa.string()), ("attribution", pa.string()), ("usage_restriction", pa.string()),
    ("collected_at_utc", pa.string()), ("processed_at_utc", pa.string()),
]])


class ClimateBuildError(Exception):
    """O candidato não passou nas verificações; a versão anterior é preservada."""


def prepare_climate(root: Path, output_dir: Path, *, processed_at_utc: str, catalog=None):
    root, output_dir = Path(root).resolve(), Path(output_dir)
    source = get_climate_source(catalog if catalog is not None else load_catalog())
    towns = load_climate_municipalities(root / "lake/silver")
    check_municipalities(towns, source["expected_municipalities"])
    codes = {town["dico"] for town in towns}
    storage = LocalStorage(root)
    states = latest_dataset_states(storage, "open_meteo")
    current = {dico: state for dico, state in states.items() if is_current_state(state, source)}
    if set(current) - codes:
        raise ClimateBuildError("município sem correspondência na dimensão CAOP")
    if not current:
        raise ClimateBuildError("nenhum município atual; execute collect_open_meteo primeiro")
    start, end = (date.fromisoformat(source["window"][key]) for key in ("start", "end"))
    output_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    with pq.ParquetWriter(output_dir / "climate_daily.parquet", SCHEMA) as writer:
        for dico, state in sorted(current.items()):
            path = storage.local_path(state["key"])
            if not path.is_file():
                raise ClimateBuildError(f"raw ausente: {state['key']}")
            digest = file_digest(path, key=state["key"], region=dico)
            if (digest["sha256"], digest["bytes"]) != (state["sha256"], state["bytes"]):
                raise ClimateBuildError(f"checksum ou tamanho alterado: {state['key']}")
            frame = read_climate_response(path)
            frame = frame[frame.variable.isin([v["id"] for v in source["variables"]])].copy()
            for key, value in {
                "source_id": "open_meteo", "dico": dico, "model": state["model"],
                "window_start": start, "window_end": end, "source_run_id": state["run_id"],
                "license_id": source["license_id"], "attribution": source.get("attribution"),
                "usage_restriction": source.get("usage_restriction"),
                "collected_at_utc": state["collected_at_utc"], "processed_at_utc": processed_at_utc,
            }.items():
                frame[key] = value
            writer.write_table(pa.Table.from_pandas(frame, schema=SCHEMA, preserve_index=False))
            count += len(frame)
    pd.DataFrame([{"variable": v["id"], "unit": v["unit"], "window_start": start, "window_end": end,
                   "expected_days": (end-start).days+1, "model": source["model"]}
                  for v in source["variables"]]).to_parquet(output_dir / "climate_meta.parquet", index=False)
    return {"observations": count, "municipalities": len(current), "variables": len(source["variables"]),
            "not_collected": sorted(codes-set(current)), "model": source["model"],
            "window": f"{start}/{end}"}


def _run_dbt(candidate: Path, silver: Path):
    executable = shutil.which("dbt")
    if executable is None:
        raise ClimateBuildError("dbt não encontrado; execute pelo ambiente uv do projeto")
    env = os.environ.copy()
    env.update({"CLIMATE_BUILD_DIR": candidate.as_posix(),
                "CLIMATE_PREPARED_DIR": (candidate / "prepared").as_posix(),
                "OBS_SILVER_DIR": silver.as_posix(),
                "CAOP_DUCKDB_PATH": (candidate / "climate.duckdb").as_posix()})
    command = [executable, "build", "--project-dir", "analytics/dbt", "--profiles-dir", "analytics/dbt",
               "--target", "local", "--select", "tag:climate"]
    result = subprocess.run(command, cwd=Path(__file__).resolve().parents[2], env=env,
                            text=True, capture_output=True, check=False)
    if result.returncode:
        detail = "\n".join((result.stdout + "\n" + result.stderr).splitlines()[-25:])
        raise ClimateBuildError(f"dbt build falhou (código {result.returncode}):\n{detail}")


def build_climate(root=Path(".data"), *, catalog=None):
    root = Path(root).resolve()
    silver = root / "lake/silver"
    parent = root / ".build/climate"
    parent.mkdir(parents=True, exist_ok=True)
    candidate = parent / uuid4().hex
    if not _canonical_path(candidate).is_relative_to(_canonical_path(parent)):
        raise ClimateBuildError("diretório temporário fora da raiz autorizada")
    candidate.mkdir()
    try:
        counts = prepare_climate(root, candidate / "prepared", processed_at_utc=utc_now(), catalog=catalog)
        for relative in PROMOTED:
            (candidate / relative).mkdir(parents=True, exist_ok=True)
        _run_dbt(candidate, silver)
        promote_paths(root, candidate, [r for r in PROMOTED if (candidate / r / "data.parquet").exists()])
        return counts
    finally:
        if candidate.exists():
            shutil.rmtree(candidate)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Constrói o staging Bronze do clima diário.")
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--root", type=Path, default=Path(".data"))
    parser.add_argument("--catalog", type=Path, help="catálogo alternativo explícito, inclusive para fixtures")
    args = parser.parse_args(argv)
    try:
        result = build_climate(args.root, catalog=load_catalog(args.catalog) if args.catalog else None)
    except (ClimateBuildError, OSError, ValueError, KeyError) as exc:
        print(f"Clima: falha: {exc}", file=sys.stderr)
        return 1
    print(f"Clima: {result['observations']} linhas de {result['municipalities']} municípios "
          f"({result['variables']} variáveis, {result['window']}, {result['model']})")
    print(f"  Bronze: {args.root / 'lake/bronze/stg_climate_daily'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
