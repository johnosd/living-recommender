"""Validação do catálogo `google_distances` antes de qualquer rede (spec 009, FR-026)."""
from copy import deepcopy

import pytest

from pipelines.collectors._shared.catalog import CatalogError, load_catalog
from pipelines.collectors.mobility.catalog import mobility_source
from tests.fixtures.mobility.responses import catalog


def source_of(**changes):
    value = deepcopy(catalog())
    value["sources"]["google_distances"].update(changes)
    return value


def test_the_fixture_catalog_and_the_real_one_are_accepted():
    assert mobility_source(catalog())["id"] == "google_distances"
    real = load_catalog()
    source = mobility_source(real)
    assert list(source["modes"]) == ["driving"]  # só o carro por decisão do autor (ADR-004)
    assert source["attribution"] == "Tempos de viagem: Google"
    assert source["pricing_verified_on"] is None  # o operador confere os preços antes de --execute


@pytest.mark.parametrize("field", ["publisher", "license_id", "attribution", "api_url", "key_env", "limits",
                                   "max_elements_per_run", "pricing", "modes", "risk_accepted", "substitution"])
def test_a_missing_field_is_rejected(field):
    value = deepcopy(catalog())
    del value["sources"]["google_distances"][field]
    with pytest.raises(CatalogError, match=field):
        mobility_source(value)


@pytest.mark.parametrize("changes", [
    {"api_url": "http://routes.googleapis.com/x"},
    {"max_elements_per_run": 0},
    {"max_elements_per_run": True},
    {"limits": {"min_interval_seconds": 0, "max_attempts": 3}},
    {"limits": {"min_interval_seconds": 1, "max_attempts": 0}},
    {"pricing_verified_on": "21/11/2026"},
    {"modes": {}},
    {"modes": {"walking": {"travel_mode": "WALK"}}},
    {"modes": {"driving": {"travel_mode": "TRANSIT"}}},
    {"window": {"start": "2026-01-01", "end": "2026-12-31"}},
    {"datasets": []},
    {"collection_method": "http_download"},
    {"pricing": {"driving": {"usd_per_1000": -1, "free_monthly": 10}}},
    {"pricing": {}},
])
def test_an_invalid_value_is_rejected(changes):
    with pytest.raises(CatalogError):
        mobility_source(source_of(**changes))


def test_transit_needs_a_weekday_departure_with_a_timezone():
    base = deepcopy(catalog()["sources"]["google_distances"])
    modes = base["modes"]
    for departure in ("2026-12-05T08:00:00Z", "2026-12-02T08:00:00", "amanhã"):  # sábado, sem fuso, texto
        broken = source_of(modes={**modes, "transit": {"travel_mode": "TRANSIT", "departure_time": departure}})
        with pytest.raises(CatalogError):
            mobility_source(broken)
    ok = source_of(modes={**modes, "transit": {"travel_mode": "TRANSIT", "departure_time": "2026-12-02T08:00:00Z"}})
    assert "transit" in mobility_source(ok)["modes"]


def test_an_unknown_source_id_is_rejected():
    with pytest.raises(CatalogError, match="não cadastrada"):
        mobility_source({"sources": {}})
