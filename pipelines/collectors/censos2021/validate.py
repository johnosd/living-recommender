"""Validação censitária separada dos indicadores municipais do INE."""

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from pipelines.collectors._shared.catalog import get_dataset_source

PRIMARY_AGES = (
    "T",
    "11",
    "12",
    "21",
    "22",
    "31",
    "32",
    "41",
    "42",
    "51",
    "52",
    "61",
    "62",
    "71",
    "72",
    "81",
    "82",
    "91",
    "92",
)
LEGACY_AGES = ("T", *(f"{n:02}" for n in range(1, 20)))
FAMILIES = {"0014632": ("2025", PRIMARY_AGES), "0011719": ("2013", LEGACY_AGES)}
PARISH_CODE = re.compile(r"[0-9]{4}[0-9A-Z]{2}")


def selected_ages(dataset):
    """Suporta snapshots históricos por idade e lotes explícitos atuais."""
    return dataset.get("age_codes", [dataset.get("age_code")])


def validate_censos_catalog(catalog):
    source = get_dataset_source(catalog, "censos")
    metadata_ids = {d["id"] for d in source["datasets"] if d.get("role") == "metadata"}
    for d in source["datasets"]:
        if d.get("indicator") not in FAMILIES or d.get("reference_period") != "2021":
            raise ValueError(f"{d['id']}: indicador/edição não suportado")
        geo, ages = FAMILIES[d["indicator"]]
        if d.get("geography_version") != geo:
            raise ValueError(f"{d['id']}: geografia incompatível")
        if d.get("role") == "metadata":
            continue
        params = d.get("params", {})
        selected = selected_ages(d)
        parishes = d.get("parish_codes")
        batch_valid = (
            (
                isinstance(parishes, list)
                and 1 <= len(parishes) <= 32
                and len(set(parishes)) == len(parishes)
                and all(
                    isinstance(x, str) and PARISH_CODE.fullmatch(x) for x in parishes
                )
                and params.get("Dim2") == ",".join(parishes)
                and "age_code" not in d
            )
            if parishes is not None
            else (params.get("Dim2") == "lvl@6" and "age_codes" not in d)
        )
        if (
            d.get("role") != "data"
            or not isinstance(selected, list)
            or not selected
            or len(set(selected)) != len(selected)
            or not set(selected) <= set(ages)
            or not batch_valid
            or params.get("Dim1") != "S7A2021"
            or params.get("Dim3") != "T"
            or params.get("Dim4") != ",".join(selected)
            or (geo == "2025" and params.get("Dim5") != "T")
            or (geo == "2013" and "Dim5" in params)
            or d.get("metadata_dataset_id") not in metadata_ids
        ):
            raise ValueError(f"{d['id']}: seletores censitários inválidos")
    return source


def query_signature(dataset):
    return hashlib.sha256(
        json.dumps(
            dataset, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


def load_document(path: Path):
    document = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if (
        not isinstance(document, list)
        or len(document) != 1
        or not isinstance(document[0], dict)
    ):
        raise ValueError("resposta INE exige exatamente um objeto")
    return document[0]


def check_document(dataset, doc):
    if not doc.get("Sucesso", {}).get("Verdadeiro") or doc.get("Sucesso", {}).get(
        "Falso"
    ):
        raise ValueError(f"{dataset['id']}: erro INE: {doc.get('Sucesso')}")
    if doc.get("IndicadorCod") != dataset["indicator"]:
        raise ValueError(f"{dataset['id']}: indicador incorreto")


def age_categories(metadata):
    rows = []
    for group in metadata.get("Dimensoes", {}).get("Categoria_Dim", []):
        for items in group.values():
            for item in items:
                if item.get("dim_num") != "4":
                    continue
                code, label = str(item["categ_cod"]), item["categ_dsg"]
                numbers = [int(x) for x in re.findall(r"\d+", label)]
                total = code == "T"
                unknown = any(
                    x in label.casefold() for x in ("ignorada", "desconhecida")
                )
                if not total and not unknown and not numbers:
                    raise ValueError(f"categoria etária sem limites: {label}")
                rows.append(
                    {
                        "age_code": code,
                        "label": label,
                        "age_min": numbers[0] if numbers else None,
                        "age_max": numbers[1] if len(numbers) == 2 else None,
                        "is_total": total,
                        "is_unknown": unknown,
                    }
                )
    frame = pd.DataFrame(rows)
    if frame.empty or frame.age_code.duplicated().any():
        raise ValueError("metadados etários vazios/duplicados")
    return frame


def parse_count(row):
    symbol = row.get("sinal_conv") or None
    if "valor" not in row or row["valor"] in (None, ""):
        label = str(row.get("sinal_conv_desc", "")).casefold()
        if symbol and ("confid" in label or str(symbol).casefold() in ("x", "c")):
            return None, "suppressed", symbol
        if symbol == "-" or "aplic" in label or "nulo" in label:
            return None, "not_applicable", symbol
        if symbol == ".." or "dispon" in label:
            return None, "not_published", symbol
        raise ValueError(f"estado ausente sem legenda reconhecida: {row}")
    try:
        value = Decimal(str(row["valor"]))
    except InvalidOperation as exc:
        raise ValueError("contagem inválida") from exc
    if not value.is_finite() or value < 0 or value != value.to_integral_value():
        raise ValueError("contagem não inteira ou negativa")
    return int(value), "observed", symbol


def validate_censos_response(dataset, path):
    doc = load_document(path)
    check_document(dataset, doc)
    if dataset["role"] == "metadata":
        age_categories(doc)
        if doc.get("PrimeiroPeriodo") != "2021" or doc.get("UltimoPeriodo") != "2021":
            raise ValueError("metadados de outra edição")
        return
    if set(doc.get("Dados", {})) != {"2021"} or not doc["Dados"]["2021"]:
        raise ValueError("resposta sem dados de 2021 ou com outro período")
    seen = set()
    ages = selected_ages(dataset)
    for row in doc["Dados"]["2021"]:
        code = str(row.get("geocod", ""))
        pair = (code, row.get("dim_4"))
        if not PARISH_CODE.fullmatch(code) or pair in seen:
            raise ValueError(f"código de freguesia inválido/duplicado: {code}")
        seen.add(pair)
        if (
            row.get("dim_3") != "T"
            or row.get("dim_4") not in ages
            or (dataset["indicator"] == "0014632" and row.get("dim_5") != "T")
        ):
            raise ValueError("dimensões da resposta diferem dos seletores")
        parse_count(row)
    if "parish_codes" in dataset and seen != {
        (code, age) for code in dataset["parish_codes"] for age in ages
    }:
        raise ValueError("lote incompleto ou com registro extra de freguesia/faixa")
