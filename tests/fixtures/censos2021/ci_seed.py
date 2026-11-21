"""Fixtures nacionais em categorias, pequenas em território, sem rede."""

import argparse
import json
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pandas as pd

from pipelines.collectors._shared.catalog import get_dataset_source, load_catalog
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors.censos2021.handler import collect_censos
from pipelines.collectors.censos2021.validate import FAMILIES
from tests.fixtures.censos2021.responses import metadata, response

PRIMARY_CODES = ["010103", "0308FC", "0308FD", "021123", "310101", "420101"]
LEGACY_CODES = ["010103", "030880", "021118", "021122", "310101", "420101"]


def fixture_metadata(indicator):
    geo, ages = FAMILIES[indicator]
    doc = deepcopy(metadata())
    doc["IndicadorCod"] = indicator
    doc["IndicadorNome"] = f"População residente, geografia {geo}"
    cats = {}
    for i, age in enumerate(ages):
        lo = (i - 1) * 5
        hi = lo + 4
        label = (
            "Total"
            if age == "T"
            else f"{lo} e mais anos"
            if i == len(ages) - 1
            else f"{lo} - {hi} anos"
        )
        cats[f"Dim_Num4_{age}"] = [
            {"dim_num": "4", "cat_id": age, "categ_cod": age, "categ_dsg": label}
        ]
    for code in PRIMARY_CODES if geo == "2025" else LEGACY_CODES:
        cats[f"Dim_Num2_{code}"] = [
            {
                "dim_num": "2",
                "cat_id": code,
                "categ_cod": code,
                "categ_dsg": code,
                "categ_nivel": "6",
            }
        ]
    doc["Dimensoes"]["Categoria_Dim"] = [cats]
    doc["Dimensoes"]["Descricao_Dim"][0]["versao"] = (
        "05723" if geo == "2025" else "04479"
    )
    return doc


def fixture_downloader(url, destination):
    q = parse_qs(urlparse(url).query)
    indicator = q["varcd"][0]
    if "pindicaMeta" in url:
        doc = fixture_metadata(indicator)
    else:
        doc = json.loads(response())[0]
        doc["IndicadorCod"] = indicator
        geo, ages = FAMILIES[indicator]
        rows = []
        for age in q["Dim4"][0].split(","):
            label = fixture_metadata(indicator)["Dimensoes"]["Categoria_Dim"][0][
                f"Dim_Num4_{age}"
            ][0]["categ_dsg"]
            codes = (
                (PRIMARY_CODES if geo == "2025" else LEGACY_CODES)
                if q["Dim2"][0] == "lvl@6"
                else q["Dim2"][0].split(",")
            )
            for code in codes:
                value = len(ages) - 1 if age == "T" else 1
                row = {
                    "geocod": code,
                    "geodsg": code,
                    "dim_3": "T",
                    "dim_3_t": "HM",
                    "dim_4": age,
                    "dim_4_t": label,
                    "valor": str(value),
                    "ind_string": str(value),
                }
                if geo == "2025":
                    row.update(dim_5="T", dim_5_t="Total")
                if code in ("0308FD", "021123") and geo == "2025":
                    row.pop("valor")
                    row.update(
                        sinal_conv="..",
                        sinal_conv_desc="Dado não disponível",
                        ind_string="..",
                    )
                rows.append(row)
        doc["Dados"] = {"2021": rows}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps([doc], ensure_ascii=False), encoding="utf8")


def fixture_catalog():
    """Dois lotes por família, com todas as idades: exercita também a união."""
    source = deepcopy(get_dataset_source(load_catalog(), "censos"))
    items = []
    for indicator, (geo, _) in FAMILIES.items():
        items.append(
            next(
                d
                for d in source["datasets"]
                if d["role"] == "metadata" and d["indicator"] == indicator
            )
        )
        template = next(
            d
            for d in source["datasets"]
            if d["role"] == "data" and d["indicator"] == indicator
        )
        codes = PRIMARY_CODES if geo == "2025" else LEGACY_CODES
        for i in range(0, len(codes), 3):
            d = deepcopy(template)
            d["id"] = f"pop_{geo}_batch_{i // 3 + 1:03}"
            d["parish_codes"] = codes[i : i + 3]
            d["params"]["Dim2"] = ",".join(d["parish_codes"])
            items.append(d)
    source["datasets"] = items
    return {"sources": {"censos": source}}


def seed(root):
    root = Path(root)
    silver = root / "lake/silver"
    dim = pd.DataFrame(
        {
            "dicofre": PRIMARY_CODES,
            "dico": [x[:4] for x in PRIMARY_CODES],
            "caop_version": ["2025"] * len(PRIMARY_CODES),
            "autonomous_region": ["continente"] * 4 + ["madeira", "acores"],
        }
    )
    crosswalk = pd.DataFrame(
        [
            ("010103", "010103", "one_to_one", False),
            ("030880", "0308FC", "one_to_many", False),
            ("030880", "0308FD", "one_to_many", False),
            ("021118", "021123", "many_to_many", True),
            ("021122", "021123", "many_to_many", True),
            ("310101", "310101", "one_to_one", False),
            ("420101", "420101", "one_to_one", False),
        ],
        columns=["dicofre_2013", "dicofre_2025", "relation", "partial_origin"],
    )
    for name, frame in [
        ("dim_parish", dim),
        ("dim_municipality", dim[["dico"]].drop_duplicates()),
        ("xwalk_parish_2013_2025", crosswalk),
    ]:
        path = silver / name / "data.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path, index=False)
    return collect_censos(
        fixture_catalog(),
        storage=LocalStorage(root),
        downloader=fixture_downloader,
        run_id="fixture",
        collected_at_utc="2026-11-13T12:00:00Z",
        work_dir=root / ".work/censos/fixture",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    seed(args.root)
    from pipelines.collectors.censos2021.prepare import prepare_censos

    summary = prepare_censos(args.root, args.root)
    from pipelines.collectors.censos2021.coverage import write_censos_reports

    write_censos_reports(summary, args.root)


if __name__ == "__main__":
    main()
