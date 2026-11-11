"""Constrói o staging Bronze de observações (Pordata e INE) a partir do estado vigente de cada dataset."""

import argparse
import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pandas as pd

from pipelines.cli._common import utc_now
from pipelines.cli._promote import promote_paths
from pipelines.collectors._shared.catalog import get_dataset_source, load_catalog
from pipelines.collectors._shared.dataset_manifest import latest_dataset_states
from pipelines.collectors._shared.manifest import file_digest
from pipelines.collectors._shared.municipality import (
    UnresolvedMunicipalities,
    resolve_municipality_names,
)
from pipelines.collectors._shared.observations import STATS_COLUMNS, finalize
from pipelines.collectors._shared.storage import LocalStorage, _canonical_path
from pipelines.collectors.ine.transform import read_ine_response
from pipelines.collectors.pordata.transform import read_pordata_csv, read_pordata_xlsx

SOURCES = ("pordata", "ine")
SYNONYMS_SEED = Path(__file__).resolve().parents[2] / "analytics" / "dbt" / "seeds" / "municipality_synonyms.csv"
PROMOTED = ("lake/bronze/stg_observation", "lake/bronze/rpt_observation_coverage")
COVERAGE_CSV = "lake/bronze/coverage.csv"


class ObservationBuildError(Exception):
    """Build das observações reprovado antes da promoção."""


def load_synonyms(path: Path = SYNONYMS_SEED) -> dict[str, str]:
    """`{grafia_exata_da_fonte: dico}`, do seed mantido à mão (só municípios)."""
    with Path(path).open(encoding="utf-8", newline="") as stream:
        return {row["source_name"]: row["dico"] for row in csv.DictReader(stream)}


def load_municipalities(silver: Path) -> dict[str, str]:
    """`{dico: nome_oficial}` da dimensão Silver da CAOP."""
    path = Path(silver) / "dim_municipality" / "data.parquet"
    if not path.is_file():
        raise ObservationBuildError("Silver da CAOP ausente; execute python -m pipelines.cli.build_caop primeiro")
    frame = pd.read_parquet(path, columns=["dico", "official_name"])
    return dict(zip(frame["dico"], frame["official_name"], strict=True))


def _reader(dataset: dict):
    method = dataset["collection_method"]
    if method == "api_json":
        return read_ine_response
    if dataset.get("format") == "xlsx":
        return read_pordata_xlsx
    return read_pordata_csv


def collect_inputs(root: Path, catalog: dict) -> tuple[list[tuple[dict, dict, dict, Path]], list[str]]:
    """Para cada dataset coletado: (fonte, dataset, estado vigente, caminho do bruto já verificado).

    Devolve também os ids (`fonte/dataset`) que ainda não foram coletados, como a planilha manual.
    """
    storage = LocalStorage(root)
    inputs, not_collected = [], []
    for source_id in SOURCES:
        source = get_dataset_source(catalog, source_id)
        states = latest_dataset_states(storage, source_id)
        for dataset in source["datasets"]:
            state = states.get(dataset["id"])
            if state is None:
                not_collected.append(f"{source_id}/{dataset['id']}")
                continue
            path = storage.local_path(state["key"])
            if not path.is_file():
                raise ObservationBuildError(f"raw ausente: {state['key']}")
            digest = file_digest(path, key=state["key"], region=dataset["id"])
            if digest["sha256"] != state["sha256"] or digest["bytes"] != state["bytes"]:
                raise ObservationBuildError(f"checksum ou tamanho alterado: {state['key']}")
            inputs.append((source, dataset, state, path))
    return inputs, not_collected


def _resolve(dataset, frame, municipalities, synonyms) -> pd.Series:
    """Série de `dico` alinhada às linhas. INE: sufixo do código; Pordata: nome + seed de sinônimos."""
    names = frame["source_name"]
    if dataset["collection_method"] == "api_json":
        unknown = sorted({code for code in names.unique() if code[-4:] not in municipalities})
        if unknown:
            raise UnresolvedMunicipalities(unknown)
        return names.str[-4:]
    mapping = resolve_municipality_names(names.unique(), municipalities, synonyms)
    return names.map(mapping)


def prepare_observations(root: Path, output_dir: Path, *, processed_at_utc: str, catalog: dict | None = None,
                         municipalities: dict[str, str] | None = None,
                         synonyms: dict[str, str] | None = None) -> dict:
    """Lê o estado vigente de cada dataset, resolve os municípios e grava o Parquet longo para o dbt."""
    root, output_dir = Path(root), Path(output_dir)
    catalog = catalog or load_catalog()
    municipalities = municipalities if municipalities is not None else load_municipalities(root / "lake" / "silver")
    synonyms = synonyms if synonyms is not None else load_synonyms()
    inputs, not_collected = collect_inputs(root, catalog)
    if not inputs:
        raise ObservationBuildError("nenhum dataset coletado; execute collect_pordata e collect_ine primeiro")

    frames, stats, failures = [], [], []
    for source, dataset, state, path in inputs:
        raw, excluded = _reader(dataset)(dataset, path)
        try:
            dico = _resolve(dataset, raw, municipalities, synonyms)
        except UnresolvedMunicipalities as exc:
            failures.append(f"{source['id']}/{dataset['id']}: {exc}")
            continue
        frames.append(finalize(raw, source=source, dataset=dataset, state=state, dico=dico,
                               processed_at_utc=processed_at_utc))
        stats.append({"source_id": source["id"], "dataset_id": dataset["id"],
                      "aggregate_rows_excluded": excluded, "rows_read": len(raw) + excluded})
    if failures:
        raise ObservationBuildError("município sem correspondência:\n  " + "\n  ".join(failures))

    output_dir.mkdir(parents=True, exist_ok=True)
    observations = pd.concat(frames, ignore_index=True)
    observations.to_parquet(output_dir / "observations.parquet", index=False)
    pd.DataFrame(stats, columns=STATS_COLUMNS).to_parquet(output_dir / "dataset_stats.parquet", index=False)
    return {"observations": len(observations), "datasets": len(frames), "not_collected": not_collected}


def write_coverage(root: Path, municipalities: dict[str, str]) -> pd.DataFrame:
    """Lê o relatório promovido e grava `coverage.csv` (separador `;`, abre no Excel) com os ausentes por nome."""
    root = Path(root)
    frame = pd.read_parquet(root / "lake" / "bronze" / "rpt_observation_coverage" / "data.parquet")
    frame = frame.sort_values(["source_id", "dataset_id"]).reset_index(drop=True)
    report = frame.copy()
    report["missing"] = report["missing_dico"].map(
        lambda codes: "; ".join(f"{code} {municipalities.get(code, '')}".strip() for code in (codes if codes is not None else []))
    )
    report.drop(columns="missing_dico").to_csv(root / COVERAGE_CSV, sep=";", index=False, encoding="utf-8-sig")
    return frame


def format_coverage(frame: pd.DataFrame, not_collected: list[str]) -> str:
    """Tabela legível: último período, municípios com valor e quantas linhas de agregação foram excluídas."""
    expected = int(frame["municipalities_expected"].iloc[0]) if len(frame) else 0
    lines = [f"Cobertura (municípios com valor no último período, de {expected}):"]
    width = max((len(f"{r.source_id}/{r.dataset_id}") for r in frame.itertuples()), default=10)
    for row in frame.itertuples():
        label = f"{row.source_id}/{row.dataset_id}"
        lines.append(
            f"  {label:<{width}}  {row.latest_period}  {row.municipalities_with_value:>3}/{row.municipalities_expected}"
            f"  sem valor: {row.municipalities_without_value:<3}  agregação excluída: {row.aggregate_rows_excluded}"
        )
    if not_collected:
        lines.append("  não coletados: " + ", ".join(not_collected))
    return "\n".join(lines)


def _run_dbt(candidate: Path, silver: Path) -> None:
    executable = shutil.which("dbt")
    if executable is None:
        raise ObservationBuildError("dbt não encontrado; execute pelo ambiente uv do projeto")
    project_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env.update({
        "OBS_BUILD_DIR": candidate.as_posix(),
        "OBS_PREPARED_DIR": (candidate / "prepared").as_posix(),
        "OBS_SILVER_DIR": Path(silver).as_posix(),
        "CAOP_DUCKDB_PATH": (candidate / "observations.duckdb").as_posix(),
    })
    command = [executable, "build", "--project-dir", "analytics/dbt", "--profiles-dir", "analytics/dbt",
               "--target", "local", "--select", "tag:observations"]
    result = subprocess.run(command, cwd=project_root, env=env, text=True, capture_output=True, check=False)
    if result.returncode:
        detail = "\n".join((result.stdout + "\n" + result.stderr).splitlines()[-25:])
        raise ObservationBuildError(f"dbt build falhou (código {result.returncode}):\n{detail}")


def build_observations(root: Path = Path(".data")) -> dict:
    """Valida o bruto, constrói em isolamento e promove só as tabelas de observações."""
    root = Path(root).resolve()
    silver = root / "lake" / "silver"
    municipalities = load_municipalities(silver)  # falha cedo se a CAOP ainda não foi construída
    parent = (root / ".build" / "observations").resolve()
    parent.mkdir(parents=True, exist_ok=True)
    candidate = (parent / uuid4().hex).resolve()
    if not _canonical_path(candidate).is_relative_to(_canonical_path(parent)):
        raise ObservationBuildError("diretório temporário fora da raiz autorizada")
    candidate.mkdir()
    try:
        counts = prepare_observations(root, candidate / "prepared", processed_at_utc=utc_now())
        for relative in PROMOTED:  # o DuckDB não cria o diretório de saída dos modelos externos
            (candidate / relative).mkdir(parents=True, exist_ok=True)
        _run_dbt(candidate, silver)
        promote_paths(root, candidate, PROMOTED)
        return {**counts, "coverage": write_coverage(root, municipalities)}
    finally:
        if candidate.exists():
            shutil.rmtree(candidate)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Constrói o staging Bronze de observações do Pordata e do INE.")
    parser.add_argument("--local", action="store_true", help="destino local (único nesta fase)")
    parser.add_argument("--root", type=Path, default=Path(".data"), help="raiz local")
    args = parser.parse_args(argv)
    try:
        result = build_observations(args.root)
    except (ObservationBuildError, UnresolvedMunicipalities, OSError, ValueError, KeyError) as exc:
        print(f"Observações: falha: {exc}", file=sys.stderr)
        return 1
    print(f"Observações: {result['observations']} linhas de {result['datasets']} datasets")
    print(f"  Bronze: {args.root / 'lake' / 'bronze' / 'stg_observation'}")
    print(format_coverage(result["coverage"], result["not_collected"]))
    print(f"  Ausentes por dataset: {args.root / COVERAGE_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
