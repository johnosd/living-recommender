"""Locked contracts for the district and region rent and its marked inheritance (spec 012).

Only the public functions of `pipelines.gold` are exercised, over small in-memory tables shaped like the lake tables
they read (`idealista_listings`, `dim_municipality`, `dim_parish`). No dbt, no files, no network.
"""
import json

import pandas as pd
import pytest

from pipelines.gold.areas import (
    AreaError,
    apply_rent_inheritance,
    district_rent_stats,
    region_rent_stats,
    territory_hierarchy,
)
from pipelines.gold.criteria import catalog_tables
from pipelines.gold.parish import parish_indicators
from pipelines.gold.quality import data_quality
from pipelines.gold.rent import parish_rent_stats, rent_indicators, rent_stats

ATTRIBUTION = "Fonte: Idealista, extração manual; período informado pelo operador"
LICENSE = "not_granted_by_source"
RESTRICTION = "somente agregados (constitution IV)"
AZORES = "Região Autónoma dos Açores"
TYPOLOGIES = {"ALL", "T0", "T1", "T2", "T3", "T4+"}


def municipalities(*rows):
    return pd.DataFrame([{"dico": dico, "district_or_island": district, "autonomous_region": autonomous}
                         for dico, district, autonomous in rows])


def listings(count, rent, *, subregion, region, typology="T2", dico=None, dicofre=None, step=10.0, month="2026-11"):
    return [{"listing_id": f"{subregion}-{dico}-{typology}-{month}-{rent}-{i}", "dico": dico, "dicofre": dicofre,
             "locality_level": "municipio" if dico else "regiao", "source_region": region,
             "source_subregion": subregion, "typology": typology, "asking_rent_eur": rent + step * i, "area_m2": 50.0,
             "snapshot_month": month, "license_id": LICENSE, "attribution": ATTRIBUTION} for i in range(count)]


def criterion(criterion_id, category, compute, *, weight=1.0, levels=("municipio",), compute_parish=None):
    item = {"id": criterion_id, "category": category, "label_pt": criterion_id, "label_en": criterion_id,
            "unit": "u", "direction": "menor_melhor", "levels": list(levels), "modes": ["peso", "faixa"],
            "default_range": [None, None], "weight": weight, "status": "disponivel", "pending_reason": None,
            "methodology_pt": "fixture", "options": None, "compute": compute}
    if compute_parish:
        item["compute_parish"] = compute_parish
    return item


def catalog(*criteria):
    names = sorted({item["category"] for item in criteria})
    return {"schema_version": 1, "categories": [{"id": name, "label_pt": name, "label_en": name} for name in names],
            "criteria": list(criteria)}


def keyed(frame, *columns):
    return {tuple(row[column] for column in columns): row for row in frame.to_dict("records")}


def test_us1_ac1_ac4_fr001_fr004_fr006_district_and_region_use_every_listing_of_the_area_with_their_own_iqr():
    towns = municipalities(("0301", "Braga", None), ("1301", "Porto", None), ("1302", "Porto", None),
                           ("4201", "Ilha de São Miguel", AZORES), ("4801", "Ilha das Flores", AZORES))
    rows = [
        *listings(12, 1000.0, subregion="Braga", region="Norte"),  # district only: no municipality
        *listings(4, 1500.0, subregion="Braga", region="Norte", typology="T3"),
        *listings(1, 99999.0, subregion="Braga", region="Norte", month="2026-10"),  # older snapshot: ignored
        *listings(6, 1200.0, subregion="Porto", region="Norte", dico="1301"),
        *listings(6, 1260.0, subregion="Porto", region="Norte", dico="1302"),
        *listings(1, 5000.0, subregion="Porto", region="Norte", dico="1301"),  # outlier of the district, not of 1301
        *listings(11, 800.0, subregion="São Miguel (Ilha dos Açores)", region="Açores", typology="T1"),
        *listings(3, 750.0, subregion="Flores (Ilha dos Açores)", region=None, typology="T1", dico="4801", step=0.0),
    ]
    frame = pd.DataFrame(rows)

    districts = district_rent_stats(frame, towns)
    regions = region_rent_stats(frame, towns)
    assert len(frame) == len(rows)  # nothing is deleted from the input
    names = {"Braga", "Porto", "Ilha de São Miguel", "Ilha das Flores"}  # CAOP names, only areas with listings
    assert set(districts["district_or_island"]) == names and len(districts) == len(names) * 6
    assert set(regions["source_region"]) == {"Norte", "Açores"} and len(regions) == 2 * 6
    for table in (districts, regions):
        assert set(table["typology"]) == TYPOLOGIES
        assert not {"listing_id", "dico", "dicofre"} & set(table.columns)  # constitution IV: aggregates only
        assert set(table["snapshot_month"]) == {"2026-11"} and set(table["source_id"]) == {"idealista"}
        assert set(table["license_id"]) == {LICENSE} and set(table["attribution"]) == {ATTRIBUTION}

    district = keyed(districts, "district_or_island", "typology")
    braga = district[("Braga", "T2")]
    assert (braga["source_region"], braga["n_listings"], braga["n_eligible"]) == ("Norte", 12, 12)
    assert (braga["rent_median"], braga["rent_p25"], braga["rent_p75"]) == pytest.approx((1055.0, 1027.5, 1082.5))
    assert braga["eur_m2_median"] == pytest.approx(21.1) and braga["sample_status"] == "suficiente"
    small = district[("Braga", "T3")]  # constitution III: no median below n = 10
    assert small["n_eligible"] == 4 and small["sample_status"] == "amostra_insuficiente"
    assert pd.isna(small["rent_median"]) and pd.isna(small["eur_m2_median"])
    assert district[("Braga", "ALL")]["rent_median"] == pytest.approx(1075.0)
    porto = district[("Porto", "T2")]
    assert (porto["n_listings"], porto["n_outliers"], porto["n_eligible"]) == (13, 1, 12)
    assert porto["rent_median"] == pytest.approx(1255.0)
    assert district[("Ilha de São Miguel", "T1")]["rent_median"] == pytest.approx(850.0)
    assert district[("Ilha das Flores", "T1")]["source_region"] == "Açores"  # from the autonomous region
    assert district[("Ilha das Flores", "T1")]["sample_status"] == "amostra_insuficiente"

    region = keyed(regions, "source_region", "typology")
    north = region[("Norte", "T2")]
    assert (north["n_listings"], north["n_outliers"], north["n_eligible"]) == (25, 1, 24)
    assert north["rent_median"] == pytest.approx(1155.0)
    assert region[("Norte", "ALL")]["n_listings"] == 29
    assert region[("Açores", "T1")]["n_eligible"] == 14
    assert region[("Açores", "T1")]["rent_median"] == pytest.approx(835.0)


def test_fr003_fr005_hierarchy_has_one_region_per_municipality_and_rejects_unknown_or_ambiguous_areas():
    towns = municipalities(("0301", "Braga", None), ("1301", "Porto", None), ("0501", "Castelo Branco", None),
                           ("4401", "Ilha da Graciosa", AZORES))
    good = [*listings(1, 900.0, subregion="Braga", region="Norte"),
            *listings(1, 900.0, subregion="Porto", region="Norte", dico="1301")]
    hierarchy = territory_hierarchy(pd.DataFrame(good), towns)
    assert len(hierarchy) == 4 and not hierarchy["dico"].duplicated().any()
    row = {item["dico"]: item for item in hierarchy.to_dict("records")}
    assert (row["0301"]["district_or_island"], row["0301"]["source_region"]) == ("Braga", "Norte")
    assert row["1301"]["source_region"] == "Norte"
    assert row["4401"]["source_region"] == "Açores"  # no listings: the autonomous region still places it
    assert pd.isna(row["0501"]["source_region"])  # mainland district without listings: never guessed

    unknown = pd.DataFrame([*good, *listings(1, 900.0, subregion="Atlantida", region="Norte")])
    for function in (territory_hierarchy, district_rent_stats):
        with pytest.raises(AreaError, match="Atlantida"):
            function(unknown, towns)
    island = "São Jorge (Ilha dos Açores)"  # a source island name without an explicit CAOP correspondence
    with pytest.raises(AreaError, match="São Jorge"):
        territory_hierarchy(pd.DataFrame([*good, *listings(1, 900.0, subregion=island, region="Açores")]), towns)
    ambiguous = pd.DataFrame([*good, *listings(1, 900.0, subregion="Braga", region="Centro")])
    with pytest.raises(AreaError, match="Braga"):
        territory_hierarchy(ambiguous, towns)


def test_us2_ac1_ac4_fr007_fr010_municipality_inherits_per_variant_from_the_finest_area_and_marks_it():
    towns = municipalities(("0301", "Braga", None), ("0401", "Bragança", None), ("0501", "Castelo Branco", None),
                           ("1301", "Porto", None), ("1302", "Porto", None))
    frame = pd.DataFrame([
        *listings(12, 1200.0, subregion="Porto", region="Norte", dico="1301"),
        *listings(3, 1600.0, subregion="Porto", region="Norte", dico="1301", typology="T3", step=0.0),
        *listings(8, 1700.0, subregion="Porto", region="Norte", dico="1302", typology="T3"),
        *listings(10, 900.0, subregion="Braga", region="Norte"),
        *listings(2, 500.0, subregion="Bragança", region="Norte", step=0.0),
    ])
    median = {"kind": "rent", "metric": "median", "variants": ["ALL", "T2", "T3"]}
    per_m2 = {"kind": "rent", "metric": "eur_m2_median", "variants": ["ALL"]}
    criteria = catalog(criterion("custo_aluguel_mediana", "custo", median, weight=0.6),
                       criterion("custo_aluguel_m2", "custo", per_m2, weight=0.4),
                       criterion("outro", "outro", {"kind": "observation"}))
    rent = rent_indicators(rent_stats(frame, towns), towns, criteria, usage_restriction=RESTRICTION)
    other = pd.DataFrame([{"dico": dico, "criterion_id": "outro", "category": "outro", "variant": "", "value": value,
                           "missing_reason": None if value is not None else "sem_publicacao", "source_id": "pordata"}
                          for dico, value in (("0301", 7.0), ("0401", None))])
    indicators = pd.concat([rent, other], ignore_index=True)
    hierarchy = territory_hierarchy(frame, towns)
    districts, regions = district_rent_stats(frame, towns), region_rent_stats(frame, towns)

    result = apply_rent_inheritance(indicators, hierarchy, districts, regions, criteria)

    assert len(result) == len(indicators) and not result.duplicated(["dico", "criterion_id", "variant"]).any()
    row = keyed(result, "dico", "criterion_id", "variant")
    expected = {  # (municipality, variant): value, origin, level
        ("1301", "ALL"): (1270.0, "proprio", "municipio"), ("1301", "T2"): (1255.0, "proprio", "municipio"),
        ("1301", "T3"): (1720.0, "herdado", "distrito"),  # own sample of 3: the variant decides on its own
        ("1302", "ALL"): (1310.0, "herdado", "distrito"), ("1302", "T2"): (1255.0, "herdado", "distrito"),
        ("0301", "ALL"): (945.0, "herdado", "distrito"), ("0301", "T2"): (945.0, "herdado", "distrito"),
        ("0301", "T3"): (1720.0, "herdado", "regiao"),  # the district has no T3 at all
        ("0401", "ALL"): (1250.0, "herdado", "regiao"), ("0401", "T2"): (1095.0, "herdado", "regiao"),
    }
    for (dico, variant), (value, origin, level) in expected.items():
        got = row[(dico, "custo_aluguel_mediana", variant)]
        assert got["value"] == pytest.approx(value), (dico, variant)
        assert (got["origin"], got["origin_level"]) == (origin, level), (dico, variant)
    for dico, value, level in (("1301", 25.4, "municipio"), ("1302", 26.2, "distrito"), ("0301", 18.9, "distrito"),
                               ("0401", 25.0, "regiao")):
        got = row[(dico, "custo_aluguel_m2", "ALL")]
        assert got["value"] == pytest.approx(value) and got["origin_level"] == level, dico

    inherited = result[result["origin"] == "herdado"]  # constitution III: inherited, never silently imputed
    assert inherited["missing_reason"].isna().all() and set(inherited["value_status"]) == {"observado"}
    for column, value in (("source_id", "idealista"), ("dataset_id", "idealista_listings"), ("period", "2026-11"),
                          ("license_id", LICENSE), ("attribution", ATTRIBUTION), ("usage_restriction", RESTRICTION)):
        assert set(inherited[column]) == {value}, column
    district = keyed(districts, "district_or_island", "typology")
    assert row[("1302", "custo_aluguel_mediana", "ALL")]["value"] == district[("Porto", "ALL")]["rent_median"]  # SC-003

    for variant in ("ALL", "T2", "T3"):  # no listings and no region for the district: absent with the own reason
        none = row[("0501", "custo_aluguel_mediana", variant)]
        assert pd.isna(none["value"]) and none["origin"] == "ausente" and pd.isna(none["origin_level"])
        assert none["missing_reason"] == "sem_anuncios"
    assert (row[("0301", "outro", "")]["origin"], row[("0301", "outro", "")]["origin_level"]) == (
        "proprio", "municipio")
    assert row[("0401", "outro", "")]["origin"] == "ausente" and pd.isna(row[("0401", "outro", "")]["value"])


def test_us2_ac5_fr011_sc004_normalization_uses_only_own_municipal_values():
    criteria = catalog(criterion("custo_aluguel_mediana", "custo",
                                 {"kind": "rent", "metric": "median", "variants": ["ALL"]}))
    base = {"criterion_id": "custo_aluguel_mediana", "variant": "ALL", "period": "2026-11", "source_id": "idealista",
            "license_id": LICENSE, "attribution": ATTRIBUTION, "usage_restriction": None}
    own = [{**base, "dico": f"{i:04d}", "value": float(i), "origin": "proprio", "origin_level": "municipio"}
           for i in range(1, 22)]
    inherited = [{**base, "dico": f"{i:04d}", "value": 1000.0, "origin": "herdado", "origin_level": "distrito"}
                 for i in range(22, 32)]
    absent = [{**base, "dico": "0099", "value": None, "origin": "ausente", "origin_level": None}]

    _, only_own = catalog_tables(criteria, {"municipio": pd.DataFrame([*own, *absent])})
    _, mixed = catalog_tables(criteria, {"municipio": pd.DataFrame([*own, *inherited, *absent])})

    got = mixed.iloc[0]
    assert (got["n"], got["min"], got["max"]) == (21, 1.0, 21.0)
    assert got["p5"] == pytest.approx(2.0) and got["p95"] == pytest.approx(20.0)
    pd.testing.assert_frame_equal(mixed.drop(columns="catalog_version"), only_own.drop(columns="catalog_version"))


def test_us3_ac1_ac2_fr012_fr014_parish_chain_keeps_the_source_level_and_quality_counts_it():
    rent = {"kind": "rent", "metric": "median", "variants": ["ALL"]}
    criteria = catalog(criterion("custo_aluguel_mediana", "custo", rent, levels=("municipio", "freguesia"),
                                 compute_parish=rent))
    parishes = pd.DataFrame({"dicofre": ["010101", "010102", "020101", "030101", "040101"],
                             "dico": ["0101", "0101", "0201", "0301", "0401"], "area_km2": [1.0] * 5})
    stats = parish_rent_stats(pd.DataFrame(listings(10, 800.0, subregion="X", region="Centro", dico="0101",
                                                    dicofre="010101", step=1.0)), parishes)

    def town(dico, value, origin, level):
        return {"dico": dico, "criterion_id": "custo_aluguel_mediana", "category": "custo", "variant": "ALL",
                "value": value, "unit": "u", "period": "2026-11", "dataset_latest_period": "2026-11",
                "is_older_period": False, "value_status": "ausente" if value is None else "observado",
                "missing_reason": "sem_anuncios" if value is None else None, "source_symbol": None,
                "source_id": "idealista", "dataset_id": "idealista_listings", "license_id": LICENSE,
                "attribution": ATTRIBUTION, "usage_restriction": None, "is_stale": False, "origin": origin,
                "origin_level": level}

    towns = pd.DataFrame([town("0101", 850.0, "proprio", "municipio"), town("0201", 950.0, "herdado", "distrito"),
                          town("0301", 1100.0, "herdado", "regiao"), town("0401", None, "ausente", None)])
    census = pd.DataFrame(columns=["dicofre", "age_code", "value"])

    parish = parish_indicators(parishes, census, towns, stats, criteria)

    assert len(parish) == 5 and "origin_level" in parish.columns
    row = {item["dicofre"]: item for item in parish.to_dict("records")}
    expected = {"010101": (804.5, "proprio", "freguesia"), "010102": (850.0, "herdado", "municipio"),
                "020101": (950.0, "herdado", "distrito"), "030101": (1100.0, "herdado", "regiao")}
    for dicofre, (value, origin, level) in expected.items():
        got = row[dicofre]
        assert got["value"] == pytest.approx(value), dicofre
        assert (got["origin"], got["origin_level"]) == (origin, level), dicofre
    assert pd.isna(row["040101"]["value"]) and row["040101"]["origin"] == "ausente"
    assert pd.isna(row["040101"]["origin_level"])

    entry = pd.DataFrame([{"catalog_version": "v1", "criterion_id": "custo_aluguel_mediana", "status": "disponivel",
                           "levels": json.dumps(["municipio", "freguesia"]), "pending_reason": None}])
    quality = data_quality(entry, {"municipio": towns, "freguesia": parish}, {})
    counts = {item["level"]: item for item in quality.to_dict("records")}
    columns = ("territories_expected", "with_value", "missing", "inherited", "inherited_municipio",
               "inherited_distrito", "inherited_regiao")
    assert tuple(counts["freguesia"][c] for c in columns) == (5, 1, 4, 3, 1, 1, 1)
    assert tuple(counts["municipio"][c] for c in columns) == (4, 1, 3, 2, 0, 1, 1)  # inherited is not own coverage
