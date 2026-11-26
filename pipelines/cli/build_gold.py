"""Constrói a camada Gold (indicadores e catálogo de critérios) em isolamento e promove tabela a tabela (spec 011).

Só lê o lake local: nenhuma rede, nenhuma chave. Qualquer falha (entrada ausente, catálogo inválido, critério
disponível sem dado, teste dbt) preserva o `lake/gold/` anterior e remove o candidato (D11).
"""
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
from pipelines.collectors._shared.storage import _canonical_path
from pipelines.gold.criteria import CriteriaError
from pipelines.gold.prepare import GoldInputError, check_inputs, prepare_gold

ROOT = Path(__file__).resolve().parents[2]
GOLD_TABLES = ("gold_municipality_indicator", "gold_rent_by_municipality_typology", "gold_municipality_climate_monthly",
               "gold_criteria_catalog", "gold_criteria_normalization", "gold_data_quality", "gold_parish_indicator",
               "gold_rent_by_parish_typology")
PROMOTED = tuple("lake/gold/" + name for name in GOLD_TABLES)


class GoldBuildError(Exception):
    """O candidato não passou nas verificações; a versão anterior de `lake/gold/` é preservada."""


def _run_dbt(candidate: Path, silver: Path) -> None:
    executable = shutil.which("dbt")
    if executable is None:
        raise GoldBuildError("dbt não encontrado; execute pelo ambiente uv do projeto")
    env = os.environ.copy()
    env.update({"GOLD_BUILD_DIR": candidate.as_posix(), "GOLD_PREPARED_DIR": (candidate / "prepared").as_posix(),
                "OBS_SILVER_DIR": silver.as_posix(), "CAOP_DUCKDB_PATH": (candidate / "gold.duckdb").as_posix()})
    # Sempre por tag (plan 002, R-007): um `dbt build` sem seleção roda modelos de outras features sem as entradas.
    command = [executable, "build", "--project-dir", "analytics/dbt", "--profiles-dir", "analytics/dbt",
               "--target", "local", "--select", "tag:gold"]
    result = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, check=False)
    if result.returncode:
        detail = "\n".join((result.stdout + "\n" + result.stderr).splitlines()[-25:])
        raise GoldBuildError(f"dbt build falhou (código {result.returncode}):\n{detail}")


def build_gold(root=Path(".data"), *, criteria_path=None) -> dict:
    root = Path(root).resolve()
    check_inputs(root)  # antes de criar o candidato: a mensagem nomeia a tabela que falta (R-010)
    parent = root / ".build/gold"
    parent.mkdir(parents=True, exist_ok=True)
    candidate = parent / uuid4().hex
    if not _canonical_path(candidate).is_relative_to(_canonical_path(parent)):
        raise GoldBuildError("diretório temporário fora da raiz autorizada")
    candidate.mkdir()
    try:
        summary = prepare_gold(root, candidate / "prepared", criteria_path=criteria_path,
                               processed_at_utc=utc_now())
        for relative in PROMOTED:
            (candidate / relative).mkdir(parents=True, exist_ok=True)
        _run_dbt(candidate, root / "lake/silver")
        promoted = promote_paths(root, candidate, PROMOTED)
        return {**summary, "promoted": promoted, "gold_dir": root / "lake/gold"}
    finally:
        if candidate.exists():
            shutil.rmtree(candidate)


def coverage_by_category(gold_dir: Path) -> pd.DataFrame:
    """Cobertura própria por categoria e nível (com valor ÷ esperados), a partir de `gold_data_quality`."""
    quality = pd.read_parquet(Path(gold_dir) / "gold_data_quality/data.parquet")
    catalog = pd.read_parquet(Path(gold_dir) / "gold_criteria_catalog/data.parquet",
                              columns=["criterion_id", "category"])
    order = list(dict.fromkeys(catalog["category"]))
    frame = quality[quality["status"] == "disponivel"].merge(catalog, on="criterion_id")
    grouped = frame.groupby(["category", "level"], sort=False)[["with_value", "territories_expected"]].sum()
    grouped = grouped.reset_index()
    grouped["_order"] = grouped["category"].map(order.index)
    return grouped.sort_values(["_order", "level"]).drop(columns="_order").reset_index(drop=True)


def pending_criteria(gold_dir: Path) -> list[tuple[str, str]]:
    quality = pd.read_parquet(Path(gold_dir) / "gold_data_quality/data.parquet")
    pending = quality[quality["status"] == "fonte_pendente"].drop_duplicates("criterion_id")
    return list(zip(pending["criterion_id"], pending["pending_reason"], strict=True))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Constrói a camada Gold: indicadores, aluguel, clima e catálogo.")
    parser.add_argument("--local", action="store_true", help="lake local (único destino nesta fase)")
    parser.add_argument("--root", type=Path, default=Path(".data"))
    parser.add_argument("--criteria", type=Path, help="config/criteria.yml alternativo, inclusive para fixtures")
    args = parser.parse_args(argv)
    try:
        result = build_gold(args.root, criteria_path=args.criteria)
    except (GoldBuildError, GoldInputError, CriteriaError, OSError, ValueError, KeyError) as exc:
        print(f"Gold: falha: {exc}", file=sys.stderr)
        return 1
    print(f"Gold: catálogo {result['catalog_version']} | {result['available']} critérios disponíveis, "
          f"{len(result['pending'])} pendentes | {result['municipalities']} municípios")
    for name, count in result["rows"].items():
        print(f"  {name}: {count} linhas")
    print("Cobertura própria por categoria (valores / esperados, todos os critérios e variantes):")
    for row in coverage_by_category(result["gold_dir"]).itertuples():
        print(f"  {row.category:<12} {row.level:<10} {row.with_value}/{row.territories_expected}")
    for criterion_id, reason in pending_criteria(result["gold_dir"]):
        print(f"  Pendente: {criterion_id} ({reason})")
    print(f"  Gold: {args.root / 'lake/gold'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
