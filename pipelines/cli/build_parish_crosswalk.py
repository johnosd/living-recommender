"""Constrói a correspondência de freguesias 2013→2025: derivação, testes no dbt e promoção por caminho (spec 004)."""

import argparse
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
from pipelines.collectors._shared.storage import LocalStorage, _canonical_path
from pipelines.collectors.parish_crosswalk.coverage import verify_coverage
from pipelines.collectors.parish_crosswalk.derive import (
    CROSSWALK_COLUMNS,
    derive_parish_crosswalk,
)
from pipelines.collectors.parish_crosswalk.handler import SOURCE_ID
from pipelines.collectors.parish_crosswalk.layout import CrosswalkSchemaError
from pipelines.collectors.parish_crosswalk.transform import (
    TABLE_A_ROLE,
    TABLE_B_ROLE,
    read_crosswalk_table,
)

PROMOTED = ("lake/silver/xwalk_parish_2013_2025", "lake/silver/rpt_parish_crosswalk_coverage")
REVIEW_CSV = "lake/silver/parish_crosswalk_review.csv"
REPORT_CSV = "lake/silver/parish_crosswalk_report.csv"
REPORT_ORDER = (*("one_to_one", "one_to_many", "many_to_one", "many_to_many"), "all")
STATS_COLUMNS = ["dataset_id", "rows_read", "ignored_rows", "numeric_codes_normalized", "partial_rows"]
RELATIONS = ("one_to_one", "one_to_many", "many_to_one", "many_to_many")
FLAGS = (
    ("inherited", "herdado"), ("partial_origin", "origem parcial"),
    ("name_changed", "nome alterado"), ("municipality_changed", "município alterado"),
)


class ParishCrosswalkBuildError(Exception):
    """Build da correspondência reprovado antes da promoção."""


def load_inputs(root: Path, catalog: dict) -> tuple[dict, dict[str, tuple[dict, dict, Path]]]:
    """Para cada papel (A e B): (dataset, estado vigente, caminho do bruto já verificado).

    Exige as duas tabelas com estado vigente, o bruto no disco e `sha256`/`bytes` conferindo (FR-015).
    """
    source = get_dataset_source(catalog, SOURCE_ID)
    by_role = {dataset.get("role"): dataset for dataset in source["datasets"]}
    storage = LocalStorage(root)
    states = latest_dataset_states(storage, SOURCE_ID)
    missing = [by_role[role]["id"] for role in (TABLE_A_ROLE, TABLE_B_ROLE) if by_role[role]["id"] not in states]
    if missing:
        raise ParishCrosswalkBuildError(
            f"tabela sem estado vigente: {', '.join(missing)}; execute python -m pipelines.cli.collect_parish_crosswalk"
        )
    inputs = {}
    for role in (TABLE_A_ROLE, TABLE_B_ROLE):
        dataset = by_role[role]
        state = states[dataset["id"]]
        path = storage.local_path(state["key"])
        if not path.is_file():
            raise ParishCrosswalkBuildError(f"raw ausente: {state['key']}")
        digest = file_digest(path, key=state["key"], region=dataset["id"])
        if digest["sha256"] != state["sha256"] or digest["bytes"] != state["bytes"]:
            raise ParishCrosswalkBuildError(f"checksum ou tamanho alterado: {state['key']}")
        inputs[role] = (dataset, state, path)
    return source, inputs


def prepare_crosswalk(root: Path, output_dir: Path, *, processed_at_utc: str, catalog: dict | None = None) -> dict:
    """Lê o estado vigente das duas tabelas, deriva a correspondência e grava o Parquet para o dbt."""
    root, output_dir = Path(root), Path(output_dir)
    catalog = catalog or load_catalog()
    source, inputs = load_inputs(root, catalog)
    (dataset_a, state_a, path_a), (dataset_b, state_b, path_b) = inputs[TABLE_A_ROLE], inputs[TABLE_B_ROLE]
    try:
        table_a, stats_a = read_crosswalk_table(dataset_a, path_a)
        table_b, stats_b = read_crosswalk_table(dataset_b, path_b)
    except CrosswalkSchemaError as exc:
        raise ParishCrosswalkBuildError(f"tabela inválida: {exc}") from exc
    crosswalk = derive_parish_crosswalk(table_a, table_b)
    crosswalk["source_run_id_2013"], crosswalk["source_run_id_2025"] = state_a["run_id"], state_b["run_id"]
    crosswalk["sha256_2013"], crosswalk["sha256_2025"] = state_a["sha256"], state_b["sha256"]
    crosswalk["license_id"], crosswalk["attribution"] = source["license_id"], source.get("attribution", "")
    crosswalk["collected_at_utc"] = max(state_a["collected_at_utc"], state_b["collected_at_utc"])
    crosswalk["processed_at_utc"] = processed_at_utc
    output_dir.mkdir(parents=True, exist_ok=True)
    crosswalk.to_parquet(output_dir / "crosswalk.parquet", index=False)
    pd.DataFrame(
        [{"dataset_id": dataset_id, **stats} for dataset_id, stats in
         ((dataset_a["id"], stats_a), (dataset_b["id"], stats_b))],
        columns=STATS_COLUMNS,
    ).to_parquet(output_dir / "table_stats.parquet", index=False)
    return {
        "pairs": len(crosswalk), "crosswalk": crosswalk, "codes_2013": set(table_a["code_2013"]),
        "stats": {dataset_a["id"]: stats_a, dataset_b["id"]: stats_b},
    }


def write_review_csv(root: Path) -> pd.DataFrame:
    """CSV para o autor: pares que não são um-para-um ou que têm algum sinal; `;` e `utf-8-sig` abrem no Excel."""
    frame = pd.read_parquet(Path(root) / PROMOTED[0] / "data.parquet")
    flagged = (frame["relation"] != "one_to_one") | frame[[name for name, _ in FLAGS]].any(axis=1)
    review = frame.loc[flagged, CROSSWALK_COLUMNS].copy()
    review["pre2013_codes"] = review["pre2013_codes"].map(lambda codes: "; ".join(codes))
    review.to_csv(Path(root) / REVIEW_CSV, sep=";", index=False, encoding="utf-8-sig")
    return frame


def write_report_csv(root: Path) -> pd.DataFrame:
    """Relatório de cobertura legível por pessoa (FR-013, US3/AC5): `;` e `utf-8-sig` abrem no Excel.

    Uma linha por natureza e a linha `all`; a versão da CAOP, a data da coleta e a atribuição são repetidas em
    **todas** as linhas (no Parquet só a linha `all` carrega os dois primeiros), para que cada linha se leia sozinha.
    """
    report = pd.read_parquet(Path(root) / PROMOTED[1] / "data.parquet")
    total = report.loc[report["relation"] == "all"].iloc[0]
    for column in ("caop_version", "collected_at_utc", "attribution"):
        report[column] = total[column]
    report["relation"] = pd.Categorical(report["relation"], categories=REPORT_ORDER, ordered=True)
    report = report.sort_values("relation").reset_index(drop=True).convert_dtypes()  # inteiros sem ".0"
    report.to_csv(Path(root) / REPORT_CSV, sep=";", index=False, encoding="utf-8-sig")
    return report


def format_summary(frame: pd.DataFrame, root: Path, parishes: int | None = None) -> str:
    counts = frame["relation"].value_counts()
    headline = (
        f"Correspondência: {len(frame)} pares ({frame['dicofre_2013'].nunique()} códigos de 2013 para "
        f"{frame['dicofre_2025'].nunique()} de 2025)"
    )
    lines = [
        headline,
        "  " + " | ".join(f"{relation}: {int(counts.get(relation, 0))}" for relation in RELATIONS),
        "  " + " | ".join(f"{label}: {int(frame[name].sum())}" for name, label in FLAGS),
        *([f"  Cobertura: {parishes} de {parishes} freguesias da dim_parish com origem"] if parishes else []),
        f"  Silver: {Path(root) / PROMOTED[0]}",
        f"  Relatório (Parquet): {Path(root) / PROMOTED[1]}",
        f"  Relatório (CSV, legível): {Path(root) / REPORT_CSV}",
        f"  Revisão (pares que não são um-para-um ou têm sinal): {Path(root) / REVIEW_CSV}",
    ]
    return "\n".join(lines)


def _run_dbt(candidate: Path, silver: Path) -> None:
    executable = shutil.which("dbt")
    if executable is None:
        raise ParishCrosswalkBuildError("dbt não encontrado; execute pelo ambiente uv do projeto")
    project_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env.update({
        "XWALK_BUILD_DIR": candidate.as_posix(),
        "XWALK_PREPARED_DIR": (candidate / "prepared").as_posix(),
        "OBS_SILVER_DIR": Path(silver).as_posix(),
        "CAOP_DUCKDB_PATH": (candidate / "crosswalk.duckdb").as_posix(),
    })
    command = [executable, "build", "--project-dir", "analytics/dbt", "--profiles-dir", "analytics/dbt",
               "--target", "local", "--select", "tag:parish_crosswalk"]
    result = subprocess.run(command, cwd=project_root, env=env, text=True, capture_output=True, check=False)
    if result.returncode:
        detail = "\n".join((result.stdout + "\n" + result.stderr).splitlines()[-25:])
        raise ParishCrosswalkBuildError(f"dbt build falhou (código {result.returncode}):\n{detail}")


def build_parish_crosswalk(root: Path = Path(".data")) -> dict:
    """Valida o bruto, constrói em isolamento e promove só as tabelas da correspondência."""
    root = Path(root).resolve()
    silver = root / "lake" / "silver"
    dim_path = silver / "dim_parish" / "data.parquet"
    if not dim_path.is_file():
        raise ParishCrosswalkBuildError(
            "Silver da CAOP (dim_parish) ausente; execute python -m pipelines.cli.build_caop primeiro"
        )
    parent = (root / ".build" / "parish_crosswalk").resolve()
    parent.mkdir(parents=True, exist_ok=True)
    candidate = (parent / uuid4().hex).resolve()
    if not _canonical_path(candidate).is_relative_to(_canonical_path(parent)):
        raise ParishCrosswalkBuildError("diretório temporário fora da raiz autorizada")
    candidate.mkdir()
    try:
        prepared = prepare_crosswalk(root, candidate / "prepared", processed_at_utc=utc_now())
        dimension = pd.read_parquet(dim_path, columns=["dicofre", "official_name"])
        verify_coverage(  # gate de cobertura (FR-012): antes do dbt, para nada ser promovido em caso de lacuna
            prepared["crosswalk"], dimension["dicofre"], prepared["codes_2013"],
            names=dict(zip(dimension["dicofre"], dimension["official_name"], strict=True)),
        )
        for relative in PROMOTED:  # o DuckDB não cria o diretório de saída dos modelos externos
            (candidate / relative).mkdir(parents=True, exist_ok=True)
        _run_dbt(candidate, silver)
        promote_paths(root, candidate, PROMOTED)
        frame = write_review_csv(root)
        write_report_csv(root)
        return {"pairs": prepared["pairs"], "parishes": len(dimension), "frame": frame}
    finally:
        if candidate.exists():
            shutil.rmtree(candidate)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Constrói a correspondência de freguesias 2013→2025.")
    parser.add_argument("--local", action="store_true", help="destino local (único nesta fase)")
    parser.add_argument("--root", type=Path, default=Path(".data"), help="raiz local")
    args = parser.parse_args(argv)
    try:
        result = build_parish_crosswalk(args.root)
    except (ParishCrosswalkBuildError, ValueError, OSError, KeyError) as exc:
        print(f"Correspondência: falha: {exc}", file=sys.stderr)
        return 1
    print(format_summary(result["frame"], args.root, result["parishes"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
