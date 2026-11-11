"""Impressão digital do INE: ignora o horário e a ordem dos registros, mas nunca uma mudança de conteúdo."""

import json
import random

from pipelines.collectors.ine.fingerprint import fingerprint_ine_response
from tests.fixtures.ine.responses import CRIME_CATEGORIES, ine_response


def _fingerprint(tmp_path, document, name="r.json"):
    path = tmp_path / name
    path.write_text(json.dumps(document), encoding="utf-8")
    return fingerprint_ine_response(path)


def _document(**options):
    return json.loads(ine_response("0008074", categories=CRIME_CATEGORIES, periods=("2021", "2022"), **options))


def test_the_same_rows_in_a_different_order_have_the_same_fingerprint(tmp_path):
    """Regressão da coleta real de 2026-11-11: a API trocou a ordem das linhas sem mudar nenhum valor."""
    original = _document()
    shuffled = _document()
    for rows in shuffled[0]["Dados"].values():
        random.Random(7).shuffle(rows)
    assert shuffled[0]["Dados"]["2022"] != original[0]["Dados"]["2022"]
    assert _fingerprint(tmp_path, original, "a.json") == _fingerprint(tmp_path, shuffled, "b.json")


def test_keys_in_a_different_order_and_another_extraction_time_do_not_change_it(tmp_path):
    first = _document(extracted_at="2026-11-11T18:00:00.000Z")
    second = _document(extracted_at="2026-11-12T09:30:00.000Z")
    second[0]["Dados"]["2021"] = [dict(reversed(list(row.items()))) for row in second[0]["Dados"]["2021"]]
    assert _fingerprint(tmp_path, first, "a.json") == _fingerprint(tmp_path, second, "b.json")


def test_a_changed_value_a_new_period_or_a_new_release_date_do_change_it(tmp_path):
    base = _fingerprint(tmp_path, _document(), "base.json")
    changed_value = _document()
    changed_value[0]["Dados"]["2022"][0]["valor"] = "999"
    new_period = _document()
    new_period[0]["Dados"]["2023"] = new_period[0]["Dados"]["2022"]
    republished = _document(published="2026-12-01")
    for index, document in enumerate((changed_value, new_period, republished)):
        assert _fingerprint(tmp_path, document, f"{index}.json") != base


def test_a_removed_row_changes_it(tmp_path):
    base = _fingerprint(tmp_path, _document(), "base.json")
    document = _document()
    document[0]["Dados"]["2022"].pop()
    assert _fingerprint(tmp_path, document, "menos.json") != base
