"""Gera, sem rede, a Silver mínima da CAOP e os brutos das duas tabelas do INE, para o dbt e os testes.

Os brutos são coletados pelo próprio coletor (`collect_parish_crosswalk`) a partir de um downloader offline, então o
resultado é um `root` que `build_parish_crosswalk` entende. O Parquet preparado também é gravado, para o passo de CI
que roda só o dbt.

    python -m tests.fixtures.parish_crosswalk.ci_seed --root .data/ci-xwalk
"""

import argparse
import tempfile
from pathlib import Path

import pandas as pd

from pipelines.cli.build_parish_crosswalk import PROMOTED, prepare_crosswalk
from pipelines.collectors._shared.catalog import get_dataset_source, load_catalog
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors.parish_crosswalk.derive import derive_parish_crosswalk
from pipelines.collectors.parish_crosswalk.handler import (
    SOURCE_ID,
    collect_parish_crosswalk,
)
from tests.fixtures.parish_crosswalk.tables import (
    make_table_a,
    make_table_b,
    offline_downloader,
    scenario_frames,
)

COLLECTED_AT = "2026-11-12T12:00:00Z"
PROCESSED_AT = "2026-11-12T13:00:00Z"
CAOP_VERSION = "2025"


def expected_crosswalk() -> pd.DataFrame:
    """A correspondência que o cenário deve produzir (derivada das tabelas normalizadas, sem passar por planilha)."""
    return derive_parish_crosswalk(*scenario_frames())


def write_silver(root: Path, *, extra_codes: tuple[str, ...] = (), drop_codes: tuple[str, ...] = ()) -> list[str]:
    """Grava a `dim_parish` mínima com os códigos de 2025 do cenário; `extra_codes`/`drop_codes` fabricam lacunas."""
    codes = sorted((set(expected_crosswalk()["dicofre_2025"]) | set(extra_codes)) - set(drop_codes))
    path = Path(root) / "lake" / "silver" / "dim_parish" / "data.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "dicofre": codes, "dico": [code[:4] for code in codes],
        "official_name": [f"Freguesia {code}" for code in codes], "caop_version": CAOP_VERSION,
    }).to_parquet(path, index=False)
    return codes


def collect_scenario(root: Path, *, rows_a=None, rows_b=None, run_id: str = "seed-1") -> dict:
    """Coleta as duas tabelas do cenário com o coletor real e um downloader offline (URLs do catálogo real)."""
    root = Path(root)
    urls = {d["id"]: d["origin"] for d in get_dataset_source(load_catalog(), SOURCE_ID)["datasets"]}
    with tempfile.TemporaryDirectory() as tmp:
        payloads = {
            urls["reorganizacao_2013"]: make_table_a(Path(tmp) / "a.xlsx", rows_a).read_bytes(),
            urls["reposicao_2025"]: make_table_b(Path(tmp) / "b.xlsx", rows_b).read_bytes(),
        }
        return collect_parish_crosswalk(
            load_catalog(), storage=LocalStorage(root), downloader=offline_downloader(payloads), run_id=run_id,
            collected_at_utc=COLLECTED_AT, work_dir=root / ".work" / run_id,
        )


def seed(root: Path) -> dict:
    root = Path(root)
    write_silver(root)
    collect_scenario(root)
    for relative in PROMOTED:  # o DuckDB não cria o diretório de saída dos modelos externos
        (root / relative).mkdir(parents=True, exist_ok=True)
    return prepare_crosswalk(root, root / "prepared", processed_at_utc=PROCESSED_AT)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera a fixture da correspondência de freguesias.")
    parser.add_argument("--root", type=Path, default=Path(".data/ci-xwalk"))
    args = parser.parse_args(argv)
    result = seed(args.root)
    print(f"fixture da correspondência: {result['pairs']} pares em {args.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
