"""Constrói Bronze/Silver locais a partir da última coleta changed da CAOP."""

import argparse
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd
from pyproj import Transformer
from shapely.geometry import Point
from shapely.wkb import loads as load_wkb

from pipelines.cli._promote import promote_paths
from pipelines.collectors._shared.manifest import file_digest, latest_changed
from pipelines.collectors._shared.storage import LocalStorage, _canonical_path
from pipelines.collectors.caop.transform import prepare_caop


class BuildError(Exception):
    """Build CAOP reprovado antes da promoção das camadas."""


def _run_dbt(candidate: Path, run_id: str) -> None:
    executable = shutil.which("dbt")
    if executable is None:
        raise BuildError("dbt não encontrado; execute pelo ambiente uv do projeto")
    project_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env.update({
        "CAOP_BUILD_DIR": candidate.as_posix(),
        "CAOP_PREPARED_DIR": (candidate / "prepared").as_posix(),
        "CAOP_DUCKDB_PATH": (candidate / "caop.duckdb").as_posix(),
        "CAOP_SOURCE_RUN_ID": run_id,
    })
    command = [
        executable, "build", "--project-dir", "analytics/dbt", "--profiles-dir", "analytics/dbt",
        "--target", "local", "--select", "tag:caop",
    ]
    result = subprocess.run(command, cwd=project_root, env=env, text=True, capture_output=True, check=False)
    if result.returncode:
        detail = "\n".join((result.stdout + "\n" + result.stderr).splitlines()[-25:])
        raise BuildError(f"dbt build falhou (código {result.returncode}):\n{detail}")


def _validate_spatial(candidate: Path, run_id: str) -> None:
    for staging, dimension, code_column in (
        ("stg_caop_municipalities", "dim_municipality", "dico"),
        ("stg_caop_parishes", "dim_parish", "dicofre"),
    ):
        bronze = pd.read_parquet(candidate / "lake" / "bronze" / staging / "data.parquet")
        silver = pd.read_parquet(candidate / "lake" / "silver" / dimension / "data.parquet")
        if len(bronze) != len(silver) or not bronze[code_column].is_unique:
            raise BuildError(f"{dimension}: contagem ou chave divergente do Bronze")
        if set(bronze[code_column]) != set(silver[code_column]):
            raise BuildError(f"{dimension}: códigos divergentes do Bronze")
        if set(silver["source_run_id"]) != {run_id}:
            raise BuildError(f"{dimension}: proveniência de outra coleta")
        joined = bronze.merge(
            silver[[code_column, "representative_lat", "representative_lon"]],
            on=code_column,
            suffixes=("_bronze", "_silver"),
            validate="one_to_one",
        )
        transformers = {}
        for row in joined.itertuples(index=False):
            crs = row.source_crs
            if crs not in transformers:
                transformers[crs] = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
            lon, lat = transformers[crs].transform(
                row.representative_lon_silver, row.representative_lat_silver
            )
            if not load_wkb(row.geometry_wkb).covers(Point(lon, lat)):
                raise BuildError(f"{dimension}: ponto fora do território: {getattr(row, code_column)}")


# Cada tabela é promovida sozinha: trocar `lake/bronze` ou `lake/silver` inteiros apagaria o staging
# de observações (spec 002), que convive com a CAOP no mesmo lake.
PROMOTED = (
    "lake/bronze/stg_caop_municipalities",
    "lake/bronze/stg_caop_parishes",
    "lake/silver/dim_municipality",
    "lake/silver/dim_parish",
)


def _promote(root: Path, candidate: Path) -> None:
    promote_paths(root, candidate, PROMOTED)


def build_caop(root: Path = Path(".data")) -> dict:
    """Valida bruto, constrói em isolamento e promove só após todos os gates."""
    root = Path(root).resolve()
    storage = LocalStorage(root)
    manifest = latest_changed(storage)
    if manifest is None:
        raise BuildError("nenhuma coleta CAOP changed encontrada; execute collect_caop primeiro")
    archives = {}
    for entry in manifest["files"]:
        path = storage.local_path(entry["key"])
        if not path.is_file():
            raise BuildError(f"raw ausente: {entry['key']}")
        digest = file_digest(path, key=entry["key"], region=entry["region"])
        if digest["sha256"] != entry["sha256"] or digest["bytes"] != entry["bytes"]:
            raise BuildError(f"checksum ou tamanho alterado: {entry['key']}")
        archives[entry["region"]] = path
    parent = (root / ".build" / "caop").resolve()
    parent.mkdir(parents=True, exist_ok=True)
    candidate = (parent / uuid4().hex).resolve()
    if not _canonical_path(candidate).is_relative_to(_canonical_path(parent)):
        raise BuildError("diretório temporário fora da raiz autorizada")
    candidate.mkdir()
    processed_at = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    try:
        counts = prepare_caop(archives, manifest, candidate / "prepared", processed_at_utc=processed_at)
        for name in ("stg_caop_municipalities", "stg_caop_parishes"):
            (candidate / "lake" / "bronze" / name).mkdir(parents=True, exist_ok=True)
        for name in ("dim_municipality", "dim_parish"):
            (candidate / "lake" / "silver" / name).mkdir(parents=True, exist_ok=True)
        _run_dbt(candidate, manifest["run_id"])
        _validate_spatial(candidate, manifest["run_id"])
        _promote(root, candidate)
        return {"run_id": manifest["run_id"], "version": manifest["version"], **counts}
    finally:
        if _canonical_path(candidate).is_relative_to(_canonical_path(parent)) and candidate.exists():
            shutil.rmtree(candidate)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Constrói Bronze/Silver da última CAOP changed.")
    parser.add_argument("--local", action="store_true", help="destino local (único nesta fase)")
    parser.add_argument("--root", type=Path, default=Path(".data"), help="raiz local")
    args = parser.parse_args(argv)
    try:
        result = build_caop(args.root)
    except (BuildError, OSError, ValueError, KeyError) as exc:
        print(f"CAOP build: falha: {exc}", file=sys.stderr)
        return 1
    print(f"CAOP build: {result['version']} | run_id={result['run_id']}")
    print(f"  {result['municipalities']} municípios; {result['parishes']} freguesias")
    print(f"  Bronze/Silver: {args.root / 'lake'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
