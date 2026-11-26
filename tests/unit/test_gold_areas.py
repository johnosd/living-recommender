"""Aluguel por distrito e região: colocação dos anúncios, paridade com o município e casos de borda (spec 012)."""
import pandas as pd
import pytest

from pipelines.collectors.idealista.territory import read_seed
from pipelines.gold.areas import (
    ISLAND_SEED,
    AreaError,
    apply_rent_inheritance,
    district_rent_stats,
    reference_levels,
    region_rent_stats,
    territory_hierarchy,
)
from pipelines.gold.criteria import CriteriaError, catalog_tables
from pipelines.gold.rent import rent_indicators, rent_stats

AZORES = "Região Autónoma dos Açores"
TOWNS = pd.DataFrame({"dico": ["0301", "1301", "4801"],
                      "district_or_island": ["Braga", "Porto", "Ilha das Flores"],
                      "autonomous_region": [None, None, AZORES]})


def listings(count, rent, *, dico=None, subregion="Braga", region="Norte", typology="T2", area=50.0):
    return [{"listing_id": f"{subregion}-{dico}-{typology}-{rent}-{i}", "dico": dico, "dicofre": None,
             "source_region": region, "source_subregion": subregion, "typology": typology,
             "asking_rent_eur": rent + 10.0 * i, "area_m2": area, "snapshot_month": "2026-11", "license_id": "L",
             "attribution": "Idealista"} for i in range(count)]


def by_key(frame, key):
    return {(row[key], row["typology"]): row for row in frame.to_dict("records")}


def test_a_district_with_one_municipality_reproduces_the_municipal_statistics():
    rows = [*listings(14, 900.0, dico="0301"), *listings(1, 9000.0, dico="0301"),
            *listings(4, 600.0, dico="0301", typology="T1"), *listings(3, 950.0, dico="0301", area=5.0)]
    frame = pd.DataFrame(rows)  # SC-005: a mesma regra nos dois níveis
    municipal = rent_stats(frame, TOWNS[TOWNS["dico"] == "0301"]).set_index("typology")
    district = district_rent_stats(frame, TOWNS).set_index("typology")
    columns = ["n_listings", "n_outliers", "n_eligible", "rent_median", "rent_p25", "rent_p75", "n_eur_m2",
               "eur_m2_median", "sample_status"]
    pd.testing.assert_frame_equal(district[columns], municipal[columns])
    assert municipal.loc["ALL", "n_outliers"] == 1


def test_blank_source_region_falls_back_to_the_autonomous_region_only():
    rows = [*listings(11, 700.0, dico="4801", subregion="Flores (Ilha dos Açores)", region=""),
            *listings(11, 900.0, region="  ")]  # continente sem região na fonte: nunca adivinhada
    frame = pd.DataFrame(rows)
    hierarchy = territory_hierarchy(frame, TOWNS).set_index("dico")
    assert hierarchy.loc["4801", "source_region"] == "Açores" and pd.isna(hierarchy.loc["0301", "source_region"])
    assert set(region_rent_stats(frame, TOWNS)["source_region"]) == {"Açores"}
    district = by_key(district_rent_stats(frame, TOWNS), "district_or_island")
    assert district[("Braga", "ALL")]["n_listings"] == 11 and pd.isna(district[("Braga", "ALL")]["source_region"])


def test_a_listing_without_district_counts_only_in_the_region():
    frame = pd.DataFrame([*listings(10, 900.0), *listings(2, 950.0, subregion=None)])
    assert by_key(district_rent_stats(frame, TOWNS), "district_or_island")[("Braga", "ALL")]["n_listings"] == 10
    assert by_key(region_rent_stats(frame, TOWNS), "source_region")[("Norte", "ALL")]["n_listings"] == 12


def test_an_unknown_municipality_code_fails_instead_of_vanishing():
    frame = pd.DataFrame(listings(1, 900.0, dico="9999"))
    for function in (territory_hierarchy, district_rent_stats, region_rent_stats):
        with pytest.raises(AreaError, match="9999"):
            function(frame, TOWNS)


def test_no_listings_gives_empty_tables_with_their_columns():
    empty = pd.DataFrame(listings(1, 900.0)).iloc[0:0]
    districts, regions = district_rent_stats(empty, TOWNS), region_rent_stats(empty, TOWNS)
    assert districts.empty and {"district_or_island", "source_region", "typology", "rent_median"} <= set(districts)
    assert regions.empty and {"source_region", "typology", "eur_m2_median", "snapshot_month"} <= set(regions)
    assert "rent_coverage" not in districts and "rent_coverage" not in regions
    hierarchy = territory_hierarchy(empty, TOWNS).set_index("dico")
    assert len(hierarchy) == 3 and hierarchy.loc["4801", "source_region"] == "Açores"


def island_scenario():
    """Flores sem amostra própria nem distrital: só há anúncios regionais dos Açores (`regional_only`)."""
    towns = pd.DataFrame({"dico": ["4801", "4201"], "district_or_island": ["Ilha das Flores", "Ilha de São Miguel"],
                          "autonomous_region": [AZORES, AZORES]})
    frame = pd.DataFrame(listings(12, 800.0, subregion="São Miguel (Ilha dos Açores)", region="Açores"))
    hierarchy = territory_hierarchy(frame, towns)
    return (towns, frame, hierarchy, district_rent_stats(frame, towns), region_rent_stats(frame, towns),
            rent_stats(frame, towns))


def test_reference_levels_adds_the_source_of_each_published_value_without_changing_the_own_coverage():
    _, _, hierarchy, districts, regions, stats = island_scenario()
    table = reference_levels(stats, hierarchy, districts, regions)
    assert list(table.columns) == [*stats.columns, "district_or_island", "source_region", "reference_level",
                                   "reference_level_eur_m2"]
    pd.testing.assert_frame_equal(table[list(stats.columns)], stats)  # FR-010: as colunas próprias não mudam
    row = by_key(table, "dico")
    flores = row[("4801", "ALL")]
    assert (flores["rent_coverage"], flores["source_region"]) == ("regional_only", "Açores")
    assert (flores["reference_level"], flores["reference_level_eur_m2"]) == ("regiao", "regiao")
    assert row[("4201", "T2")]["reference_level"] == "distrito"
    assert pd.isna(row[("4201", "T1")]["reference_level"]) and pd.isna(row[("4801", "T1")]["reference_level"])


def criteria_for(*variants):
    compute = {"kind": "rent", "metric": "median", "variants": list(variants)}
    item = {"id": "custo_aluguel_mediana", "category": "custo", "label_pt": "a", "label_en": "a", "unit": "u",
            "direction": "menor_melhor", "levels": ["municipio"], "modes": ["peso"], "default_range": [None, None],
            "weight": 1.0, "status": "disponivel", "pending_reason": None, "methodology_pt": "m", "options": None,
            "compute": compute}
    return {"schema_version": 1, "categories": [{"id": "custo", "label_pt": "c", "label_en": "c"}], "criteria": [item]}


def test_a_regional_only_island_inherits_the_region():
    towns, _, hierarchy, districts, regions, stats = island_scenario()
    criteria = criteria_for("T2", "T1")
    result = apply_rent_inheritance(rent_indicators(stats, towns, criteria), hierarchy, districts, regions, criteria)
    row = by_key(result.rename(columns={"variant": "typology"}), "dico")
    assert (row[("4801", "T2")]["origin"], row[("4801", "T2")]["origin_level"]) == ("herdado", "regiao")
    absent = row[("4801", "T1")]  # nenhum nível tem T1: o motivo próprio continua
    assert (absent["origin"], absent["missing_reason"]) == ("ausente", "regional_only")


def test_normalization_has_no_row_without_own_values_and_a_criterion_without_any_fails():
    own = {"dico": "0001", "criterion_id": "custo_aluguel_mediana", "variant": "ALL", "value": 900.0,
           "origin": "proprio", "origin_level": "municipio"}
    inherited = {**own, "variant": "T2", "value": 950.0, "origin": "herdado", "origin_level": "distrito"}
    _, normalization = catalog_tables(criteria_for("ALL", "T2"), {"municipio": pd.DataFrame([own, inherited])})
    assert normalization["variant"].tolist() == ["ALL"]  # R-004: T2 só herdado fica sem parâmetros
    with pytest.raises(CriteriaError, match="'custo_aluguel_mediana'"):
        catalog_tables(criteria_for("ALL", "T2"), {"municipio": pd.DataFrame([inherited])})


def test_the_island_seed_has_one_row_per_source_name():
    rows = read_seed(ISLAND_SEED)
    sources = [row["source_subregion"] for row in rows]
    assert len(sources) == len(set(sources)) and all(row["district_or_island"].startswith("Ilha") for row in rows)
