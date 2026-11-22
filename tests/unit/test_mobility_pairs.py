"""Elegibilidade e itens de coleta (spec 009, FR-013/014, logic/pares-e-estados.md §2–§4)."""
from collections import Counter
from pathlib import Path

import pytest

from pipelines.collectors.mobility.catalog import mobility_source
from pipelines.collectors.mobility.pairs import (
    build_items,
    eligible,
    is_identity,
    pair_id,
    route_pairs,
)
from pipelines.collectors.mobility.poles import load_poles, resolve_poles
from tests.fixtures.mobility.responses import catalog, municipalities, raw_poles

ROOT = Path(__file__).resolve().parents[2]


def setup():
    towns = municipalities()
    return towns, resolve_poles(raw_poles(), towns)


def test_pair_id_is_dico_pole_mode():
    assert pair_id("0101", "aeroporto_x", "driving") == "0101--aeroporto_x--driving"


def test_eligibility_follows_group_and_scope():
    towns, poles = setup()
    town = {t["dico"]: t for t in towns}
    pole = {p["pole_id"]: p for p in poles}
    assert eligible(town["0102"], pole["cidade_a"]) and eligible(town["0201"], pole["aeroporto_x"])
    assert not eligible(town["3101"], pole["cidade_a"])  # island municipality, mainland national pole
    assert not eligible(town["0101"], pole["sede_b"])  # other district
    assert eligible(town["0201"], pole["sede_b"])
    assert eligible(town["3101"], pole["funchal"]) and not eligible(town["3102"], pole["funchal"])  # other island
    assert not eligible(town["0101"], pole["funchal"])


def test_identity_only_for_the_municipality_of_a_non_airport_pole():
    towns, poles = setup()
    town = {t["dico"]: t for t in towns}
    pole = {p["pole_id"]: p for p in poles}
    assert is_identity(town["0101"], pole["cidade_a"]) and not is_identity(town["0102"], pole["cidade_a"])
    assert not is_identity(town["0101"], pole["aeroporto_x"])


def test_route_pairs_are_sorted_and_respect_the_enabled_modes():
    towns, poles = setup()
    both = route_pairs(towns, poles)
    assert [p["id"] for p in both] == sorted(p["id"] for p in both)
    assert Counter(p["mode"] for p in both) == {"driving": 8, "transit": 8}
    assert {p["mode"] for p in route_pairs(towns, poles, ("driving",))} == {"driving"}


def test_build_items_skip_identity_and_carry_the_request_fields_without_a_key():
    towns, poles = setup()
    source = mobility_source(catalog())
    items = build_items(source, towns, poles)
    assert len(items) == 10 and [i["id"] for i in items] == sorted(i["id"] for i in items)
    item = next(i for i in items if i["id"] == "0102--aeroporto_x--driving")
    assert (item["origin_lat"], item["origin_lon"]) == (39.0, -9.0) and (item["dest_lat"], item["dest_lon"]) == (38.78, -9.13)
    assert item["travel_mode"] == "DRIVE" and item["routing_preference"] == "TRAFFIC_UNAWARE"
    assert item["departure_time"] is None and item["collection_method"] == "api_json"
    transit = next(i for i in items if i["id"] == "0102--aeroporto_x--transit")
    assert transit["departure_time"] == source["modes"]["transit"]["departure_time"]
    assert "key" not in " ".join(item)


def test_the_real_catalog_yields_the_expected_pair_counts():
    from pipelines.collectors._shared.catalog import load_catalog
    from pipelines.collectors.mobility.municipalities import (
        load_mobility_municipalities,
    )

    silver = ROOT / ".data/lake/silver"
    if not (silver / "dim_municipality/data.parquet").is_file():
        pytest.skip("dimensão CAOP real ausente (só existe localmente)")
    towns = load_mobility_municipalities(silver)
    poles = load_poles(ROOT / "config/poles.yml", towns)
    items = build_items(mobility_source(load_catalog()), towns, poles)
    # 5 polos nacionais x 278 do continente - 2 identidades (Lisboa, Porto) + Madeira (FNC) + São Miguel (PDL)
    assert len(items) == 5 * 278 - 2 + 10 + 6 == 1404
    assert {item["mode"] for item in items} == {"driving"}
    only_straight_line = {t["dico"] for t in towns} - {item["dico"] for item in items}
    assert len(only_straight_line) == 14  # Porto Santo e as 13 cidades das outras ilhas dos Açores
