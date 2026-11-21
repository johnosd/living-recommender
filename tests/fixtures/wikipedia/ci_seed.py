"""Raiz sintética nova para o build offline Wikipedia, sem rede."""

import argparse
import csv
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors.wikipedia.handler import collect_wikipedia
from pipelines.collectors.wikipedia.identity import FIELDS
from pipelines.collectors.wikipedia.local import file_hash
from tests.fixtures.wikipedia.responses import (
    associations,
    catalog,
    fetcher,
    municipalities,
)


def seed(root, *, absent=False):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError("fixture exige raiz nova/vazia")
    dimension = root / "lake/silver/dim_municipality/data.parquet"
    dimension.parent.mkdir(parents=True)
    pq.write_table(pa.Table.from_pylist(municipalities(), schema=pa.schema([
        ("dico", pa.string()), ("official_name", pa.string()), ("caop_version", pa.string())])), dimension)
    mapping = associations()
    if absent:
        mapping[1].update(status="absent", page_id=None, title="", evidence_quote="",
                          evidence_note="Busca e candidatos revisados: nenhum artigo municipal apropriado em português.")
    (root / "catalog.yml").write_text(yaml.safe_dump(catalog(), allow_unicode=True), encoding="utf-8")
    with (root / "associations.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(mapping)
    fetch, _ = fetcher()
    result = collect_wikipedia(catalog(), municipalities=municipalities(), associations=mapping,
        territory_hash=file_hash(dimension), storage=LocalStorage(root), fetcher=fetch, run_id="fixture",
        collected_at_utc="2026-11-20T10:00:00Z", work_dir=root / "work")
    assert result["status"] == "changed"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    seed(args.root)
    print(f"Wikipedia fixture preparada em {args.root}")


if __name__ == "__main__":
    main()
