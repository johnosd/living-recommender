"""Validação e resolução dos polos (spec 009, FR-001/002/004)."""
from copy import deepcopy
from pathlib import Path

import pytest

from pipelines.collectors.mobility.poles import (
    PoleError,
    load_poles,
    poles_catalog_version,
    resolve_poles,
)
from tests.fixtures.mobility.responses import municipalities, raw_poles

ROOT = Path(__file__).resolve().parents[2]


def with_change(target, **changes):
    poles = deepcopy(raw_poles())
    pole = next(pole for pole in poles if pole["pole_id"] == target)
    pole.update(changes)
    return poles


def test_valid_poles_are_resolved_with_the_municipality_point():
    poles = {pole["pole_id"]: pole for pole in resolve_poles(raw_poles(), municipalities())}
    assert list(poles) == sorted(poles)  # deterministic order
    assert (poles["cidade_a"]["latitude"], poles["cidade_a"]["longitude"]) == (38.0, -9.0)
    assert poles["funchal"]["district_or_island"] == "Ilha da Madeira"
    assert poles["aeroporto_x"]["dico"] is None and poles["aeroporto_x"]["source_ref"] == "fixture"


@pytest.mark.parametrize(("pole_id", "changes", "message"), [
    ("cidade_a", {"pole_id": "aeroporto_x"}, "repetido"),
    ("cidade_a", {"pole_id": "Cidade A"}, "inválido"),
    ("cidade_a", {"dico": "9999"}, "dico inexistente"),
    ("cidade_a", {"dico": None}, "dico inexistente"),
    ("cidade_a", {"latitude": 38.0, "longitude": -9.0}, "ponto do município"),
    ("sede_b", {"routing_group": "madeira"}, "diverge"),
    ("cidade_a", {"kind": "estacao"}, "kind"),
    ("cidade_a", {"scope": "global"}, "scope"),
    ("cidade_a", {"campo_novo": 1}, "campo desconhecido"),
    ("cidade_a", {"name": " "}, "name"),
    ("aeroporto_x", {"latitude": None}, "coordenadas"),
    ("aeroporto_x", {"latitude": 50.0}, "fora de Portugal"),
    ("aeroporto_x", {"longitude": -40.0}, "fora de Portugal"),
    ("aeroporto_x", {"source_ref": ""}, "source_ref"),
    ("aeroporto_x", {"dico": "0101"}, "não referencia"),
    ("aeroporto_x", {"routing_group": "madeira"}, "national"),
    ("sede_b", {"scope": "national"}, "sede_distrito"),
    ("funchal", {"scope": "district"}, "district"),
    ("funchal", {"routing_group": "continente"}, "island"),
])
def test_each_rule_rejects_the_whole_catalog_and_names_the_pole(pole_id, changes, message):
    with pytest.raises(PoleError, match=message) as error:
        resolve_poles(with_change(pole_id, **changes), municipalities())
    assert isinstance(error.value, ValueError)


def test_an_island_airport_needs_its_island():
    poles = deepcopy(raw_poles())
    poles.append({"pole_id": "aeroporto_ilha", "name": "Aeroporto", "kind": "aeroporto", "routing_group": "madeira",
                  "scope": "island", "latitude": 32.7, "longitude": -16.8, "source_ref": "fixture"})
    with pytest.raises(PoleError, match="aeroporto_ilha.*district_or_island"):
        resolve_poles(poles, municipalities())
    poles[-1]["district_or_island"] = "Ilha da Madeira"
    assert any(pole["pole_id"] == "aeroporto_ilha" for pole in resolve_poles(poles, municipalities()))


def test_an_empty_or_non_list_catalog_is_rejected():
    for value in ([], None, {"poles": []}):
        with pytest.raises(PoleError):
            resolve_poles(value, municipalities())


def test_the_catalog_version_ignores_input_order_and_changes_with_any_pole():
    towns = municipalities()
    first = resolve_poles(raw_poles(), towns)
    assert poles_catalog_version(first) == poles_catalog_version(list(reversed(first)))
    assert poles_catalog_version(first) != poles_catalog_version(
        resolve_poles(with_change("aeroporto_x", latitude=38.79), towns))


def test_load_poles_reads_the_yaml_and_requires_version_one(tmp_path):
    path = tmp_path / "poles.yml"
    path.write_text("version: 2\npoles: []\n", encoding="utf-8")
    with pytest.raises(PoleError, match="version"):
        load_poles(path, municipalities())
    path.write_text("version: 1\npoles:\n  - {pole_id: cidade_a, name: A, kind: cidade, routing_group: continente,"
                    " scope: national, dico: '0101'}\n", encoding="utf-8")
    assert [pole["pole_id"] for pole in load_poles(path, municipalities())] == ["cidade_a"]


def test_the_real_poles_file_resolves_against_the_real_dimension():
    from pipelines.collectors.mobility.municipalities import (
        load_mobility_municipalities,
    )

    silver = ROOT / ".data/lake/silver"
    if not (silver / "dim_municipality/data.parquet").is_file():
        pytest.skip("dimensão CAOP real ausente (só existe localmente)")
    towns = load_mobility_municipalities(silver)
    poles = load_poles(ROOT / "config/poles.yml", towns)
    assert [pole["pole_id"] for pole in poles] == ["aeroporto_fao", "aeroporto_fnc", "aeroporto_lis",
                                                   "aeroporto_opo", "aeroporto_pdl", "lisboa", "porto"]
    assert len(towns) == 308
