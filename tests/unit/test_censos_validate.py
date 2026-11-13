"""Validação antes de persistir e identidade da consulta."""

import json
from copy import deepcopy

import pytest

from pipelines.collectors.censos2021.validate import (
    query_signature,
    validate_censos_response,
)
from tests.fixtures.censos2021.responses import dataset, response


@pytest.mark.parametrize(
    "case",
    ["api_error", "indicator", "aggregate", "decimal", "negative", "age", "period"],
)
def test_bad_responses_are_rejected(tmp_path, case):
    doc = json.loads(response())
    row = doc[0]["Dados"]["2021"][0]
    if case == "api_error":
        doc[0]["Sucesso"] = {"Falso": [{"Msg": "erro"}]}
    if case == "indicator":
        doc[0]["IndicadorCod"] = "0"
    if case == "aggregate":
        row["geocod"] = "0101"
    if case == "decimal":
        row["valor"] = "1.5"
    if case == "negative":
        row["valor"] = "-1"
    if case == "age":
        row["dim_4"] = "32"
    if case == "period":
        doc[0]["Dados"]["2011"] = doc[0]["Dados"].pop("2021")
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(doc), encoding="utf8")
    with pytest.raises(ValueError):
        validate_censos_response(dataset(), path)


def test_query_identity_contains_selectors_and_geography():
    first = dataset()
    second = deepcopy(first)
    second["geography_evidence"] = "new official evidence"
    assert query_signature(first) != query_signature(second)
