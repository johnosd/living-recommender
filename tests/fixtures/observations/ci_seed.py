"""Gera, sem rede, uma Silver sintética da CAOP e brutos de Pordata e INE, para dbt e testes.

Os brutos são coletados pelos próprios coletores (`collect_pordata`, `collect_ine`) a partir de
downloaders offline, então o resultado é um `root` que `build_observations` entende.

    python -m tests.fixtures.observations.ci_seed --root .data/ci-obs
"""

import argparse
import json
from pathlib import Path

import pandas as pd

from pipelines.cli.build_observations import prepare_observations
from pipelines.collectors._shared.catalog import get_dataset_source, load_catalog
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors.ine.fetch import build_url
from pipelines.collectors.ine.handler import collect_ine
from pipelines.collectors.pordata.handler import collect_pordata
from tests.fixtures.ine.responses import CRIME_CATEGORIES, ine_response
from tests.fixtures.pordata.layouts import offline_downloader, pordata_csv

COLLECTED_AT = "2026-11-11T12:00:00Z"
PROCESSED_AT = "2026-11-11T13:00:00Z"
GENERIC_COUNT = 303
# dico: (nome oficial na CAOP, grafia usada pelo Pordata). São os 5 casos reais que exigem sinônimo.
SPECIAL = {
    "0806": ("Lagoa", "Lagoa"),
    "4201": ("Lagoa", "Lagoa [R.A.A.]"),
    "3101": ("Calheta", "Calheta [R.A.M.]"),
    "4501": ("Calheta de São Jorge", "Calheta [R.A.A.]"),
    "4302": ("Praia da Vitória", "Vila da Praia da Vitória"),
}


def municipalities() -> dict[str, tuple[str, str]]:
    """308 municípios: 303 genéricos e os 5 casos especiais. `{dico: (oficial, grafia do Pordata)}`."""
    generic = {f"{number:04d}": (f"Município {number:04d}",) * 2 for number in range(1, GENERIC_COUNT + 1)}
    return {**generic, **SPECIAL}


def write_silver(root: Path) -> dict[str, str]:
    """Grava a Silver mínima (`dico`, `official_name`) e devolve `{dico: nome oficial}`."""
    mapping = {dico: official for dico, (official, _) in municipalities().items()}
    path = Path(root) / "lake" / "silver" / "dim_municipality" / "data.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"dico": list(mapping), "official_name": list(mapping.values())}).to_parquet(path, index=False)
    return mapping


def blank_latest_period(text: str) -> str:
    """Esvazia o período mais recente de uma resposta do INE: todos passam a `sinal_conv: "-"`, sem `valor`."""
    document = json.loads(text)
    rows = document[0]["Dados"][document[0]["UltimoPref"]]
    for row in rows:
        row.pop("valor", None)
        row.update({"sinal_conv": "-", "sinal_conv_desc": "Dado nulo ou não aplicável", "ind_string": "-"})
    return json.dumps(document, ensure_ascii=False)


def seed(root: Path, *, prepare: bool = True, ine_missing_count: int = 10, rendas_latest_empty: bool = False) -> dict:
    """Silver + brutos coletados; com ``prepare`` também grava o Parquet longo em ``<root>/prepared``.

    ``ine_missing_count`` municípios ficam sem valor em todos os indicadores do INE;
    ``rendas_latest_empty`` esvazia só o período mais recente das rendas.
    """
    root = Path(root)
    write_silver(root)
    for table in ("stg_observation", "rpt_observation_coverage"):  # o DuckDB não cria o diretório de saída
        (root / "lake" / "bronze" / table).mkdir(parents=True, exist_ok=True)
    catalog, storage = load_catalog(), LocalStorage(root)
    names = tuple(pordata for _, pordata in municipalities().values())
    http = [d for d in get_dataset_source(catalog, "pordata")["datasets"] if d["collection_method"] == "http_download"]
    texts = {
        dataset["origin"]: pordata_csv(
            "abc"[index % 3], municipalities=names, years=(2023, 2024), with_symbols=index == 0,
            unit=f" unidades-{index}",
        )
        for index, dataset in enumerate(http)
    }
    collect_pordata(catalog, storage=storage, downloader=offline_downloader(texts), run_id="ci-obs-pordata",
                    collected_at_utc=COLLECTED_AT, work_dir=root / ".work" / "pordata")

    geocodes = [(f"999{dico}", official) for dico, (official, _) in municipalities().items()]
    missing = tuple(code for code, _ in geocodes[:ine_missing_count])
    ine_texts = {}
    for dataset in get_dataset_source(catalog, "ine")["datasets"]:
        options = {"categories": CRIME_CATEGORIES} if dataset["id"] == "taxa_criminalidade" else {}
        text = ine_response(dataset["indicator"], municipalities=geocodes, missing=missing, **options)
        if rendas_latest_empty and dataset["id"] == "rendas_novos_contratos":
            text = blank_latest_period(text)
        ine_texts[build_url(dataset)] = text
    collect_ine(catalog, storage=storage, downloader=offline_downloader(ine_texts), run_id="ci-obs-ine",
                collected_at_utc=COLLECTED_AT, work_dir=root / ".work" / "ine")

    counts = {"municipalities": len(municipalities()), "http_datasets": len(http)}
    if prepare:
        counts.update(prepare_observations(root, root / "prepared", processed_at_utc=PROCESSED_AT))
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera a fixture sintética de observações para o dbt.")
    parser.add_argument("--root", type=Path, default=Path(".data/ci-obs"))
    root = parser.parse_args().root
    if root.exists() and any(root.iterdir()):  # os run_id da fixture são fixos: não regerar por cima
        parser.error(f"{root} já existe e não está vazio; apague-o ou use outro --root")
    print(seed(root))


if __name__ == "__main__":
    main()
