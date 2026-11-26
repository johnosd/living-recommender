"""Validação de `config/criteria.yml` (spec 011, contracts/criteria-catalog.md §1.1)."""
import copy
from collections import defaultdict
from pathlib import Path

import pytest
import yaml

from pipelines.gold.criteria import CriteriaError, load_criteria

ROOT = Path(__file__).resolve().parents[2]
REAL = ROOT / "config/criteria.yml"


def base() -> dict:
    observation = {"kind": "observation", "source_id": "pordata", "dataset_id": "d", "filters": [{}],
                   "dash_is_zero": False}
    return {"schema_version": 1,
            "categories": [{"id": "a", "label_pt": "A", "label_en": "A"}],
            "criteria": [{"id": "a1", "category": "a", "label_pt": "x", "label_en": "x", "unit": "u",
                          "direction": "maior_melhor", "levels": ["municipio"], "modes": ["peso", "faixa"],
                          "default_range": [None, None], "weight": 1.0, "status": "disponivel",
                          "pending_reason": None, "methodology_pt": "m", "options": None,
                          "compute": copy.deepcopy(observation)}]}


def write(tmp_path: Path, document: dict) -> Path:
    path = tmp_path / "criteria.yml"
    path.write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")
    return path


def test_real_catalog_loads_and_category_weights_add_up_to_one():
    criteria = load_criteria(REAL)
    totals = defaultdict(float)
    for item in criteria["criteria"]:
        if item["status"] == "disponivel" and item["weight"] > 0:
            totals[item["category"]] += item["weight"]
    assert {category["id"] for category in criteria["categories"]} == set(totals)
    assert all(total == pytest.approx(1.0) for total in totals.values()), totals
    pending = [item["id"] for item in criteria["criteria"] if item["status"] == "fonte_pendente"]
    assert pending == ["distancia_sede_distrito_km"]


def test_minimal_catalog_is_valid(tmp_path):
    assert load_criteria(write(tmp_path, base()))["criteria"][0]["id"] == "a1"


def mutate_criterion(**changes):
    def apply(document):
        document["criteria"][0].update(changes)
    return apply


def add_second(document, **changes):
    second = copy.deepcopy(document["criteria"][0])
    second.update({"id": "a2", **changes})
    document["criteria"].append(second)


CASES = {
    "id repetido": (lambda d: add_second(d, id="a1", weight=0.0), "'a1'"),
    "categoria inexistente": (mutate_criterion(category="zz"), "'a1'"),
    "categoria repetida": (lambda d: d["categories"].append({"id": "a", "label_pt": "A", "label_en": "A"}), "'a'"),
    "direction inválida": (mutate_criterion(direction="melhor"), "'a1'"),
    "levels vazio": (mutate_criterion(levels=[]), "'a1'"),
    "level desconhecido": (mutate_criterion(levels=["distrito"]), "'a1'"),
    "modes vazio": (mutate_criterion(modes=[]), "'a1'"),
    "status inválido": (mutate_criterion(status="talvez"), "'a1'"),
    "pendente sem motivo": (lambda d: add_second(d, status="fonte_pendente", pending_reason=None, weight=0.0),
                            "'a2'"),
    "disponível sem compute": (mutate_criterion(compute=None), "'a1'"),
    "pesos não somam 1": (lambda d: add_second(d, weight=0.5), "'a'"),
    "categoria só com peso 0": (mutate_criterion(weight=0.0), "'a'"),
    "peso fora de 0 a 1": (mutate_criterion(weight=1.5), "'a1'"),
    "opcao sem options": (mutate_criterion(modes=["opcao"], options=None), "'a1'"),
    "opcao com uma option": (mutate_criterion(modes=["opcao"], options=[
        {"id": "x", "label_pt": "X", "label_en": "X", "range": [None, 1]}]), "'a1'"),
    "option sem range": (mutate_criterion(modes=["opcao"], options=[
        {"id": "x", "label_pt": "X", "label_en": "X"}, {"id": "y", "label_pt": "Y", "label_en": "Y",
                                                         "range": [1, None]}]), "'a1'"),
    "default_range invertido": (mutate_criterion(default_range=[10, 1]), "'a1'"),
    "observation sem dataset_id": (lambda d: d["criteria"][0]["compute"].pop("dataset_id"), "'a1'"),
    "dois denominadores": (lambda d: d["criteria"][0]["compute"].update(
        per_population={"scale": 1, "age_groups": None}, presence=True), "'a1'"),
    "minutes em linha reta": (mutate_criterion(compute={"kind": "mobility", "mode": "straight_line",
                                                        "measure": "minutes", "pole_id": "lisboa"}), "'a1'"),
    "polo fixo e mais próximo": (mutate_criterion(compute={"kind": "mobility", "mode": "driving", "measure": "km",
                                                           "pole_id": "lisboa", "nearest_kind": "aeroporto"}),
                                 "'a1'"),
    "métrica de clima desconhecida": (mutate_criterion(compute={"kind": "climate", "metric": "umidade"}), "'a1'"),
    "census no município": (mutate_criterion(compute={"kind": "census", "metric": "residentes"}), "'a1'"),
    "compute_parish sem freguesia": (mutate_criterion(compute_parish={"kind": "census", "metric": "residentes"}),
                                     "'a1'"),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_each_rule_raises_criteria_error_quoting_the_id(tmp_path, case):
    change, quoted = CASES[case]
    document = base()
    change(document)
    with pytest.raises(CriteriaError, match=quoted):
        load_criteria(write(tmp_path, document))


def test_pending_criterion_does_not_need_compute_or_weight_sum(tmp_path):
    document = base()
    document["categories"].append({"id": "b", "label_pt": "B", "label_en": "B"})
    document["criteria"].append({**copy.deepcopy(document["criteria"][0]), "id": "b1", "category": "b",
                                 "status": "fonte_pendente", "pending_reason": "sem fonte", "compute": None,
                                 "weight": 0.0})
    assert len(load_criteria(write(tmp_path, document))["criteria"]) == 2
