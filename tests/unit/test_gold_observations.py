"""Indicadores de observações: presence, share, filtros com NBSP e símbolos (spec 011, logic/indicadores.md §1)."""
import pandas as pd
import pytest

from pipelines.gold.observations import municipal_indicators

PORDATA = {"source_id": "pordata", "license_id": "not_granted_by_source", "attribution": "Fonte: PORDATA"}


def obs(dataset_id, dico, period, value, symbol=None, filter_1="", filter_2=""):
    return {**PORDATA, "dataset_id": dataset_id, "dico": dico, "period": period, "filter_1": filter_1,
            "filter_2": filter_2, "filter_3": "", "value": value, "symbol": symbol}


def catalog(*items):
    return {"schema_version": 1, "categories": [{"id": "c", "label_pt": "c", "label_en": "c"}], "criteria": list(items)}


def criterion(criterion_id, compute, status="disponivel"):
    return {"id": criterion_id, "category": "c", "unit": "u", "levels": ["municipio"], "status": status,
            "compute": compute}


def rows_by_dico(frame, criterion_id):
    return {row["dico"]: row for row in frame[frame["criterion_id"] == criterion_id].to_dict("records")}


TOWNS = pd.DataFrame({"dico": ["0101", "0102", "0103"]})


def test_presence_turns_dash_into_zero_and_any_positive_count_into_one():
    data = pd.DataFrame([obs("ensino_superior", "0101", 2025, 3.0, filter_1="Total"),
                         obs("ensino_superior", "0102", 2025, None, "-", filter_1="Total"),
                         obs("ensino_superior", "0103", 2024, 1.0, filter_1="Total")])
    compute = {"kind": "observation", "dataset_id": "ensino_superior", "filters": [{"filter_1": "Total"}],
               "dash_is_zero": True, "presence": True}
    result = rows_by_dico(municipal_indicators(data, TOWNS, catalog(criterion("sup", compute))), "sup")
    assert result["0101"]["value"] == 1.0 and result["0101"]["value_status"] == "observado"
    assert result["0102"]["value"] == 0.0 and result["0102"]["value_status"] == "zero_convencao_fonte"
    assert result["0103"]["value"] == 1.0 and result["0103"]["is_older_period"]


def test_share_divides_by_a_line_of_the_same_dataset_and_period_with_nbsp_labels():
    section = "A. \xa0Agricultura,  produção animal"
    data = pd.DataFrame([obs("pessoal", "0101", 2023, 25.0, filter_1=section),
                         obs("pessoal", "0101", 2023, 100.0, filter_1="Total"),
                         obs("pessoal", "0101", 2022, 999.0, filter_1="Total"),
                         obs("pessoal", "0102", 2023, 10.0, filter_1=section)])  # sem total: sem denominador
    compute = {"kind": "observation", "dataset_id": "pessoal", "dash_is_zero": True,
               "filters": [{"filter_1": "A. Agricultura, produção animal"}],
               "share": {"filters": {"filter_1": "Total"}, "scale": 100}}
    result = rows_by_dico(municipal_indicators(data, TOWNS, catalog(criterion("a", compute))), "a")
    assert result["0101"]["value"] == pytest.approx(25.0) and result["0101"]["period"] == "2023"
    assert result["0102"]["missing_reason"] == "sem_denominador" and result["0102"]["period"] == "2023"
    assert result["0103"]["missing_reason"] == "sem_publicacao"


def test_pending_and_other_kinds_are_ignored():
    data = pd.DataFrame([obs("d", "0101", 2024, 1.0)])
    observed = {"kind": "observation", "dataset_id": "d", "filters": [{}], "dash_is_zero": False}
    criteria = catalog(criterion("ok", observed), criterion("pendente", observed, status="fonte_pendente"),
                       criterion("clima", {"kind": "climate", "metric": "tci_anual"}))
    result = municipal_indicators(data, TOWNS, criteria)
    assert set(result["criterion_id"]) == {"ok"} and len(result) == 3


def test_revised_and_provisional_values_stay_observed_with_the_symbol():
    data = pd.DataFrame([obs("d", "0101", 2024, 5.0, "r"), obs("d", "0102", 2024, 6.0, "Pro")])
    compute = {"kind": "observation", "dataset_id": "d", "filters": [{}], "dash_is_zero": False}
    result = rows_by_dico(municipal_indicators(data, TOWNS, catalog(criterion("d", compute))), "d")
    assert (result["0101"]["value_status"], result["0101"]["source_symbol"]) == ("observado", "r")
    assert (result["0102"]["value_status"], result["0102"]["source_symbol"]) == ("observado", "Pro")


def test_a_missing_part_of_the_numerator_falls_back_to_the_previous_complete_year():
    data = pd.DataFrame([obs("d", "0101", 2023, 1.0, filter_1="a"), obs("d", "0101", 2023, 2.0, filter_1="b"),
                         obs("d", "0101", 2024, 5.0, filter_1="a"),  # 2024 sem a parte "b"
                         obs("d", "0102", 2024, 1.0, filter_1="a"), obs("d", "0102", 2024, 1.0, filter_1="b")])
    compute = {"kind": "observation", "dataset_id": "d", "filters": [{"filter_1": "a"}, {"filter_1": "b"}],
               "dash_is_zero": False}
    result = rows_by_dico(municipal_indicators(data, TOWNS, catalog(criterion("d", compute))), "d")
    assert result["0101"]["value"] == pytest.approx(3.0) and result["0101"]["period"] == "2023"
    assert result["0101"]["is_older_period"] and result["0101"]["dataset_latest_period"] == "2024"
