"""Tabelas do catálogo: normalização, opções, proveniência distinta (spec 011, contracts/criteria-catalog.md §2)."""
import json

import pandas as pd
import pytest

from pipelines.gold.criteria import catalog_tables


def criterion(criterion_id, *, weight=1.0, modes=("peso", "faixa"), options=None, levels=("municipio",)):
    return {"id": criterion_id, "category": "c", "label_pt": criterion_id, "label_en": criterion_id, "unit": "u",
            "direction": "faixa_alvo", "levels": list(levels), "modes": list(modes), "default_range": [1, 5],
            "weight": weight, "status": "disponivel", "pending_reason": None, "methodology_pt": "m",
            "options": options, "compute": {"kind": "observation"}}


def rows(criterion_id, values, *, period="2024", license_id="L1", variant=""):
    return pd.DataFrame({"dico": [f"{i:04d}" for i in range(len(values))], "criterion_id": criterion_id,
                         "variant": variant, "value": values, "period": period, "source_id": "s",
                         "dataset_id": "d", "license_id": license_id, "attribution": "A", "usage_restriction": None})


OPTIONS = [{"id": "baixo", "label_pt": "Baixo", "label_en": "Low", "range": [None, 10]},
           {"id": "alto", "label_pt": "Alto", "label_en": "High", "range": [10, None]}]


@pytest.fixture
def tables():
    criteria = {"schema_version": 1, "categories": [{"id": "c", "label_pt": "Cat", "label_en": "Cat"}],
                "criteria": [criterion("plano"), criterion("filtro", weight=0.0, modes=("faixa",)),
                             criterion("opcao", weight=0.0, modes=("opcao", "faixa"), options=OPTIONS)]}
    frame = pd.concat([rows("plano", [3.0, 3.0, 3.0]),
                       rows("filtro", [1.0, 2.0], period="2023", license_id="L2"),
                       rows("filtro", [5.0], period="2024", license_id="L1").assign(dico="0009"),
                       rows("opcao", [1.0, 20.0])], ignore_index=True)
    catalog, normalization = catalog_tables(criteria, {"municipio": frame})
    return ({row["criterion_id"]: row for row in catalog.to_dict("records")},
            {row["criterion_id"]: row for row in normalization.to_dict("records")})


def test_degenerate_distribution_is_flagged(tables):
    _, normalization = tables
    assert normalization["plano"]["is_degenerate"] and normalization["plano"]["p5"] == 3.0
    assert not normalization["filtro"]["is_degenerate"]


def test_zero_weight_filter_and_categorical_options_are_catalogued(tables):
    catalog, _ = tables
    assert catalog["filtro"]["weight"] == 0.0 and json.loads(catalog["filtro"]["modes"]) == ["faixa"]
    assert json.loads(catalog["opcao"]["options"]) == OPTIONS
    assert pd.isna(catalog["plano"]["options"])
    assert (catalog["plano"]["default_range_min"], catalog["plano"]["default_range_max"]) == (1.0, 5.0)
    assert catalog["plano"]["category_label_pt"] == "Cat"


def test_reference_periods_and_licenses_are_distinct_and_sorted(tables):
    catalog, _ = tables
    assert json.loads(catalog["filtro"]["reference_periods"]) == ["2023", "2024"]
    assert catalog["filtro"]["license_ids"] == "L1 | L2"
    assert pd.isna(catalog["plano"]["usage_restrictions"])


def test_parish_normalization_counts_only_own_values():
    criteria = {"schema_version": 1, "categories": [{"id": "c", "label_pt": "c", "label_en": "c"}],
                "criteria": [criterion("p", levels=("municipio", "freguesia"))]}
    parish = rows("p", [1.0, 2.0, 100.0]).assign(origin=["proprio", "proprio", "herdado"])
    _, normalization = catalog_tables(criteria, {"municipio": rows("p", [1.0]), "freguesia": parish})
    level = normalization[normalization["level"] == "freguesia"].iloc[0]
    assert (level["n"], level["max"]) == (2, 2.0)
