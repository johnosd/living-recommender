"""Perfil de freguesia: próprio, herdado e ausente (spec 011, US3, D9)."""
import pandas as pd
import pytest

from pipelines.gold.criteria import catalog_tables
from pipelines.gold.parish import parish_indicators
from pipelines.gold.rent import parish_rent_stats

CENSOS = {"license_id": "CC-BY-4.0", "attribution": "INE Censos", "period": "2021"}
RENT = {"kind": "rent", "metric": "median", "variants": ["ALL"]}


def criterion(criterion_id, category, compute, compute_parish=None, levels=("municipio",)):
    item = {"id": criterion_id, "category": category, "label_pt": criterion_id, "label_en": criterion_id,
            "unit": "u", "direction": "maior_melhor", "levels": list(levels), "modes": ["peso"],
            "default_range": [None, None], "weight": 1.0, "status": "disponivel", "pending_reason": None,
            "methodology_pt": "m", "options": None, "compute": compute}
    if compute_parish:
        item["compute_parish"] = compute_parish
    return item


CRITERIA = {"schema_version": 1,
            "categories": [{"id": name, "label_pt": name, "label_en": name}
                           for name in ("populacao", "custo", "clima", "distancia")],
            "criteria": [
                criterion("residentes", "populacao", {"kind": "observation"}, {"kind": "census", "metric": "residentes"},
                          levels=("municipio", "freguesia")),
                criterion("aluguel", "custo", RENT, RENT, levels=("municipio", "freguesia")),
                criterion("tci", "clima", {"kind": "climate", "metric": "tci_anual"}),
                criterion("lisboa", "distancia", {"kind": "mobility"})]}

PARISHES = pd.DataFrame({"dicofre": ["010101", "010102", "020101"], "dico": ["0101", "0101", "0201"],
                         "area_km2": [10.0, 5.0, 8.0]})


def municipal_row(dico, criterion_id, category, value, variant="", source="pordata", reason=None):
    return {"dico": dico, "criterion_id": criterion_id, "category": category, "variant": variant, "value": value,
            "unit": "u", "period": "2024", "dataset_latest_period": "2024", "is_older_period": False,
            "value_status": "observado" if value is not None else "ausente",
            "missing_reason": reason if value is None else None, "source_symbol": None, "source_id": source,
            "dataset_id": "d", "license_id": "L", "attribution": "A", "usage_restriction": None, "is_stale": False}


def listings():
    rows = [{"listing_id": f"A{i}", "dico": "0101", "dicofre": "010101", "typology": "T2",
             "asking_rent_eur": 800.0 + i, "area_m2": 50.0} for i in range(10)]
    rows += [{"listing_id": f"B{i}", "dico": "0101", "dicofre": "010102", "typology": "T2", "asking_rent_eur": 900.0,
              "area_m2": 50.0} for i in range(3)]
    frame = pd.DataFrame(rows)
    return frame.assign(snapshot_month="2026-11", source_region="Centro", license_id="L", attribution="Idealista")


@pytest.fixture(scope="module")
def parish():
    census = pd.DataFrame([{**CENSOS, "dicofre": "010101", "age_code": "T", "value": 1000,
                            "coverage_status": "own"},
                           {**CENSOS, "dicofre": "010102", "age_code": "T", "value": 500,
                            "coverage_status": "inherited"}])
    municipal = pd.DataFrame([
        municipal_row("0101", "residentes", "populacao", 20000.0), municipal_row("0201", "residentes", "populacao", 900.0),
        municipal_row("0101", "aluguel", "custo", 850.0, variant="ALL", source="idealista"),
        municipal_row("0201", "aluguel", "custo", None, variant="ALL", source="idealista", reason="sem_anuncios"),
        municipal_row("0101", "tci", "clima", 40.0, source="open_meteo"),
        municipal_row("0201", "tci", "clima", 42.0, source="open_meteo"),
        municipal_row("0101", "lisboa", "distancia", 120.0, source="google_distances"),
        municipal_row("0201", "lisboa", "distancia", None, source="google_distances", reason="sem_par_elegivel")])
    stats = parish_rent_stats(listings(), PARISHES)
    frame = parish_indicators(PARISHES, census, municipal, stats, CRITERIA)
    return frame, {(row["dicofre"], row["criterion_id"]): row for row in frame.to_dict("records")}


def test_every_parish_appears_once_per_criterion_and_variant(parish):
    frame, _ = parish
    assert len(frame) == 3 * 4 and not frame.duplicated(["dicofre", "criterion_id", "variant"]).any()


def test_census_value_is_own_even_when_the_census_inherited_the_territory(parish):
    _, row = parish
    inherited = row[("010102", "residentes")]
    assert (inherited["origin"], inherited["value"], inherited["territorial_inheritance"]) == (
        "proprio", 500.0, "inherited")
    assert inherited["source_id"] == "censos" and inherited["period"] == "2021"
    assert row[("010101", "residentes")]["territorial_inheritance"] == "own"
    no_census = row[("020101", "residentes")]  # sem Censos: herda o município
    assert (no_census["origin"], no_census["value"]) == ("herdado", 900.0)


def test_rent_is_own_with_ten_listings_inherited_below_and_absent_when_the_municipality_has_none(parish):
    _, row = parish
    own = row[("010101", "aluguel")]
    assert own["origin"] == "proprio" and own["value"] == pytest.approx(804.5) and own["source_id"] == "idealista"
    small = row[("010102", "aluguel")]
    assert (small["origin"], small["value"], small["period"]) == ("herdado", 850.0, "2024")
    absent = row[("020101", "aluguel")]
    assert absent["origin"] == "ausente" and pd.isna(absent["value"]) and absent["missing_reason"] == "sem_anuncios"


def test_climate_and_mobility_are_always_inherited_exact_copies(parish):
    _, row = parish
    climate = row[("010101", "tci")]
    assert (climate["origin"], climate["value"], climate["source_id"], climate["license_id"]) == (
        "herdado", 40.0, "open_meteo", "L")
    assert pd.isna(climate["territorial_inheritance"])
    mobility = row[("020101", "lisboa")]
    assert mobility["origin"] == "ausente" and mobility["missing_reason"] == "sem_par_elegivel"


def test_parish_normalization_ignores_inherited_values(parish):
    frame, _ = parish
    # perfil municipal falso: sem a coluna `origin` da freguesia, que no município só normaliza `proprio` (spec 012)
    municipal = frame.drop(columns=["dicofre", "origin", "origin_level"], errors="ignore").drop_duplicates(
        ["dico", "criterion_id", "variant"])
    municipal = municipal.assign(value=municipal["value"].fillna(1.0))
    _, normalization = catalog_tables(CRITERIA, {"municipio": municipal, "freguesia": frame})
    residents = normalization[(normalization["criterion_id"] == "residentes")
                              & (normalization["level"] == "freguesia")].iloc[0]
    assert (residents["n"], residents["min"], residents["max"]) == (2, 500.0, 1000.0)
