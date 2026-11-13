"""Fixture sem rede, dados de terceiros ou dependência da extração real."""

import argparse
import json
from pathlib import Path

import pandas as pd

from pipelines.collectors._shared.catalog import load_catalog
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors.idealista.prepare import prepare_snapshot
from pipelines.collectors.idealista.snapshot import import_snapshot

NOW = "2026-11-13T12:00:00Z"


def seed(root: Path, *, prepare=True):
    root = Path(root).resolve()
    for name, frame in {
        "dim_municipality": pd.DataFrame({"dico": ["1312", "1106", "0101"],
                                          "official_name": ["Porto", "Lisboa", "Águeda"]}),
        "dim_parish": pd.DataFrame({"dicofre": ["131203", "110601"], "dico": ["1312", "1106"],
                                   "official_name": ["Bonfim", "Ajuda"]}),
    }.items():
        path = root / "lake" / "silver" / name / "data.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path, index=False)
    source = root.parent / f"{root.name}-manual-source"
    files = {
        "norte/Porto-Paginas1.json": [
            {"id": "101", "Titulo": "Apartamento, Bonfim", "Preco": "1.200€/mês", "tipologia": "T2", "areaBrutaM2": 80},
            {"id": "102", "Titulo": "Apartamento, Local desconhecido", "Preco": None, "tipologia": "T1", "areaBrutaM2": None},
        ],
        "norte/Porto-Paginas2.json": [
            {"id": "101", "Titulo": "Apartamento, Bonfim", "Preco": "1.500€/mês", "tipologia": "T2", "areaBrutaM2": 80},
        ],
        "lisboa/Ajuda-Paginas1.json": [
            {"id": "103", "Titulo": "Apartamento", "Preco": "900€/mês", "tipologia": "T0", "areaBrutaM2": 40},
        ],
        "Acores/arrendar-casas-acores-Paginas1.json": [
            {"id": "104", "Titulo": "Apartamento", "Preco": "750€/mês", "tipologia": "T5", "areaBrutaM2": 120},
        ],
    }
    for relative, rows in files.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    manifest = import_snapshot(load_catalog(), storage=LocalStorage(root), directory=source,
                               snapshot_month="2025-08", run_id="fixture", imported_at_utc=NOW)
    if prepare:
        prepare_snapshot(root, root / "prepared", snapshot_month="2025-08", processed_at_utc=NOW)
        for relative in ("lake/bronze/idealista_occurrences", "lake/silver/idealista_listings"):
            (root / relative).mkdir(parents=True, exist_ok=True)
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(".data/ci-idealista"))
    seed(parser.parse_args().root)


if __name__ == "__main__":
    main()
