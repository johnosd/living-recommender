"""Locked contracts for the Gold indicators and the criteria catalog (spec 011).

Only the public functions of `pipelines.gold` are exercised, over small in-memory tables shaped like the lake
tables they read (`stg_observation`, `stg_climate_daily`, `idealista_listings`, `stg_municipality_pole_distance`).
No dbt, no files, no network.
"""
from datetime import date, timedelta

import pandas as pd
import pytest

from pipelines.gold.climate import climate_monthly
from pipelines.gold.criteria import CriteriaError, catalog_tables
from pipelines.gold.mobility import mobility_indicators
from pipelines.gold.observations import municipal_indicators
from pipelines.gold.rent import rent_stats

PORDATA = {"source_id": "pordata", "license_id": "not_granted_by_source", "attribution": "Fonte: PORDATA"}
CAOP_ATTRIBUTION = "Fonte: Direção-Geral do Território (DGT), CAOP2025"
GOOGLE_ATTRIBUTION = "Tempos de viagem: Google"
GOOGLE_RESTRICTION = "termos da Google Maps Platform; guardar a matriz de tempos é risco aceito (ADR-002 D8)"
POPULATION = "populacao_residente_sexo_idade"


def criterion(criterion_id, compute, *, category="cat", weight=1.0, status="disponivel", levels=("municipio",)):
    return {"id": criterion_id, "category": category, "label_pt": criterion_id, "label_en": criterion_id,
            "unit": "u", "direction": "maior_melhor", "levels": list(levels), "modes": ["peso", "faixa"],
            "default_range": [None, None], "weight": weight, "status": status,
            "pending_reason": None if status == "disponivel" else "fixture: fonte ainda não coletada",
            "methodology_pt": "fixture", "options": None, "compute": compute}


def catalog(*criteria, categories=None):
    names = categories or sorted({item["category"] for item in criteria})
    return {"schema_version": 1, "categories": [{"id": name, "label_pt": name, "label_en": name} for name in names],
            "criteria": list(criteria)}


def by_key(frame):
    return {(row["dico"], row["criterion_id"]): row for row in frame.to_dict("records")}


def obs(dataset_id, dico, period, value, symbol=None, filter_1="", filter_2=""):
    return {**PORDATA, "dataset_id": dataset_id, "dico": dico, "source_name": dico, "period": period,
            "filter_1": filter_1, "filter_2": filter_2, "filter_3": "", "value": value, "symbol": symbol,
            "unit": "u", "source_run_id": "run-1"}


def test_us1_ac1_ac4_fr001_fr003_fr004_fr005_latest_period_per_municipality_same_year_population_and_dash_rule():
    municipalities = pd.DataFrame({"dico": ["0101", "0102", "0103", "0104"]})
    ages = ("25 - 29 anos", "30 - 34 anos", "35 - 39 anos")
    rows = [
        obs(POPULATION, "0101", 2023, 10000.0, filter_1="Total", filter_2="Total"),
        obs(POPULATION, "0101", 2024, 20000.0, filter_1="Total", filter_2="Total"),
        obs(POPULATION, "0102", 2024, 5000.0, filter_1="Total", filter_2="Total"),
        obs(POPULATION, "0103", 2022, 8000.0, filter_1="Total", filter_2="Total"),
        *[obs(POPULATION, "0101", 2024, value, filter_1="Total", filter_2=age)
          for age, value in zip(ages, (2000.0, 2000.0, 1000.0), strict=True)],
        obs("recintos_cinema", "0101", 2023, 3.0),
        obs("recintos_cinema", "0101", 2024, 4.0),
        obs("recintos_cinema", "0102", 2024, None, "-"),  # a count dataset: "-" is zero by the source convention
        obs("recintos_cinema", "0103", 2022, 2.0),  # older than the national 2024: used, and flagged
        obs("recintos_cinema", "0104", 2024, 1.0),  # no population in 2024: no denominator
        obs("ganho_medio_mensal", "0101", 2022, 900.0),
        obs("ganho_medio_mensal", "0101", 2023, 1000.0),
        obs("ganho_medio_mensal", "0102", 2023, None, "-"),  # a mean, not a count: "-" stays absent
        obs("ganho_medio_mensal", "0103", 2023, None, "x"),
    ]
    criteria = catalog(
        criterion("cultura_cinemas_10k", {"kind": "observation", "source_id": "pordata",
                                          "dataset_id": "recintos_cinema", "filters": [{}], "dash_is_zero": True,
                                          "per_population": {"scale": 10000, "age_groups": None}},
                  category="cultura"),
        criterion("emprego_ganho_medio_mensal", {"kind": "observation", "source_id": "pordata",
                                                 "dataset_id": "ganho_medio_mensal", "filters": [{}],
                                                 "dash_is_zero": False}, category="emprego"),
        criterion("populacao_pct_25_39", {"kind": "observation", "source_id": "pordata", "dataset_id": POPULATION,
                                          "filters": [{"filter_1": "Total", "filter_2": age} for age in ages],
                                          "dash_is_zero": True,
                                          "share": {"filters": {"filter_1": "Total", "filter_2": "Total"},
                                                    "scale": 100}}, category="populacao"),
    )
    result = municipal_indicators(pd.DataFrame(rows), municipalities, criteria)
    assert len(result) == 4 * 3 and not result.duplicated(["dico", "criterion_id", "variant"]).any()
    row = by_key(result)

    cinema = row[("0101", "cultura_cinemas_10k")]  # 4 / 20000 (2024), never the 2023 population
    assert cinema["value"] == pytest.approx(2.0) and cinema["period"] == "2024" and not cinema["is_older_period"]
    assert cinema["value_status"] == "observado" and cinema["dataset_latest_period"] == "2024"
    assert (cinema["license_id"], cinema["attribution"], cinema["dataset_id"]) == (
        "not_granted_by_source", "Fonte: PORDATA", "recintos_cinema")
    zero = row[("0102", "cultura_cinemas_10k")]
    assert zero["value"] == 0.0 and zero["value_status"] == "zero_convencao_fonte" and zero["source_symbol"] == "-"
    older = row[("0103", "cultura_cinemas_10k")]
    assert older["value"] == pytest.approx(2.5) and older["period"] == "2022" and older["is_older_period"]
    assert older["dataset_latest_period"] == "2024"
    no_denominator = row[("0104", "cultura_cinemas_10k")]
    assert pd.isna(no_denominator["value"]) and no_denominator["value_status"] == "ausente"
    assert no_denominator["missing_reason"] == "sem_denominador"

    wage = row[("0101", "emprego_ganho_medio_mensal")]
    assert wage["value"] == pytest.approx(1000.0) and wage["period"] == "2023" and not wage["is_older_period"]
    for dico, reason in (("0102", "simbolo_fonte:-"), ("0103", "simbolo_fonte:x"), ("0104", "sem_publicacao")):
        absent = row[(dico, "emprego_ganho_medio_mensal")]  # constitution III: nothing is imputed
        assert pd.isna(absent["value"]) and absent["value_status"] == "ausente" and absent["missing_reason"] == reason

    assert row[("0101", "populacao_pct_25_39")]["value"] == pytest.approx(25.0)
    assert row[("0102", "populacao_pct_25_39")]["missing_reason"] == "sem_publicacao"
    assert result.loc[result["value"].isna(), "missing_reason"].notna().all()  # every absence has a reason


def test_us1_ac2_ac3_fr020_fr021_fr022_fr024_catalog_fails_on_available_without_data_and_versions_every_change():
    def indicators(values):
        return pd.DataFrame({"dico": [f"{i:04d}" for i in range(1, len(values) + 1)], "criterion_id": "a1",
                             "variant": "", "value": values, "period": "2024", **PORDATA, "usage_restriction": None})

    def build(a1_weight=0.5, a2_weight=0.5, values=None, a2_values=(5.0, None)):
        criteria = catalog(criterion("a1", {"kind": "observation"}, category="a", weight=a1_weight),
                           criterion("a2", {"kind": "observation"}, category="a", weight=a2_weight),
                           criterion("b1", {"kind": "observation"}, category="b", status="fonte_pendente"))
        a2 = pd.DataFrame({"dico": ["0001", "0002"], "criterion_id": "a2", "variant": "", "value": list(a2_values),
                           "period": "2024", **PORDATA, "usage_restriction": None})
        frame = pd.concat([indicators(values or [float(v) for v in range(1, 22)]), a2], ignore_index=True)
        return catalog_tables(criteria, {"municipio": frame})

    entries, normalization = build()
    assert set(entries["criterion_id"]) == {"a1", "a2", "b1"}
    status = dict(zip(entries["criterion_id"], entries["status"], strict=True))
    assert status == {"a1": "disponivel", "a2": "disponivel", "b1": "fonte_pendente"}  # pending: no data, no failure
    a1 = normalization[(normalization["criterion_id"] == "a1") & (normalization["level"] == "municipio")].iloc[0]
    assert (a1["n"], a1["min"], a1["max"]) == (21, 1.0, 21.0)
    assert a1["p5"] == pytest.approx(2.0) and a1["p95"] == pytest.approx(20.0)  # linear interpolation
    assert "b1" not in set(normalization["criterion_id"])
    version = entries["catalog_version"].iloc[0]
    assert entries["catalog_version"].nunique() == 1 and set(normalization["catalog_version"]) == {version}

    assert build()[0]["catalog_version"].iloc[0] == version  # same definitions and data: same version
    assert build(0.6, 0.4)[0]["catalog_version"].iloc[0] != version  # a definition changed
    changed = [float(v) for v in range(1, 22)]
    changed[-1] = 99.0
    assert build(values=changed)[0]["catalog_version"].iloc[0] != version  # a normalization parameter changed

    with pytest.raises(CriteriaError, match="'a2'"):  # messages quote the id: see contracts/criteria-catalog.md
        build(a2_values=(None, None))  # available, but no municipality has a value
    with pytest.raises(CriteriaError, match="'a'"):
        build(0.5, 0.4)  # the weights of category "a" do not add up to 1


def test_us1_ac6_fr015_fr016_fr018_tci_bands_and_extreme_days_follow_the_legacy_rules():
    month = [date(2024, 11, 1) + timedelta(days=offset) for offset in range(30)]
    rows = []

    def day(dico, when, **values):
        defaults = {"temperature_2m_mean": 18.0, "temperature_2m_max": 22.0, "temperature_2m_min": 12.0,
                    "apparent_temperature_max": 22.0, "apparent_temperature_min": 10.0,
                    "relative_humidity_2m_mean": 60.0, "precipitation_sum": 0.0, "snowfall_sum": 0.0,
                    "sunshine_duration": 6 * 3600.0, "wind_speed_10m_mean": 10.0}
        for variable, value in {**defaults, **values}.items():
            rows.append({"source_id": "open_meteo", "dico": dico, "variable": variable, "date": when, "value": value})

    # (tmean, tmax, humidity, daily rain mm, sun hours, wind km/h) -> (CID, CIA, P, S, W, TCI); every band edge
    bands = {
        "0001": ((20.0, 27.0, 50.0, 1.0, 9.0, 14.9), (10, 10, 10, 10, 10, 60.0)),
        "0002": ((19.9, 27.1, 30.0, 2.0, 7.0, 15.0), (7, 7, 7, 7, 7, 42.0)),
        "0003": ((13.0, 33.0, 50.0, 3.0, 5.0, 25.0), (5, 5, 5, 5, 5, 30.0)),
        "0004": ((10.0, 36.0, 50.0, 4.0, 3.0, 35.0), (3, 3, 3, 3, 3, 18.0)),
        "0005": ((9.9, 36.1, 95.0, 4.1, 2.9, 45.0), (-1, -1, 0, 0, 0, 0.0)),  # below zero is clamped to 0
        "0006": ((16.0, 30.0, 29.9, 0.0, 9.0, 0.0), (6, 6, 10, 10, 10, 44.0)),  # humidity < 30: one point less
        "0007": ((27.0, 20.0, 90.0, 0.0, 12.0, 0.0), (10, 10, 10, 10, 10, 60.0)),  # 90 % is not above 90
    }
    for dico, ((tmean, tmax, humidity, rain, sun, wind), _) in bands.items():
        for when in month:
            day(dico, when, temperature_2m_mean=tmean, temperature_2m_max=tmax, relative_humidity_2m_mean=humidity,
                precipitation_sum=rain, sunshine_duration=sun * 3600.0, wind_speed_10m_mean=wind)

    extremes = {  # day of the month -> values; the limits themselves are not extreme
        1: {"temperature_2m_max": 35.0, "apparent_temperature_max": 40.0},
        2: {"temperature_2m_max": 35.1},  # hot
        3: {"apparent_temperature_max": 40.1},  # hot (in place of the legacy heat index)
        4: {"temperature_2m_min": 1.0, "apparent_temperature_min": -5.0},
        5: {"temperature_2m_min": 0.9},  # cold
        6: {"apparent_temperature_min": -5.1},  # cold (in place of the legacy wind chill)
        7: {"precipitation_sum": 35.0},
        8: {"precipitation_sum": 35.1},  # rain
        9: {"snowfall_sum": 0.01},  # snow: any positive value
        10: {"temperature_2m_max": 36.0, "precipitation_sum": 40.0},  # hot and rain: one extreme day
    }
    for when in month:
        day("0099", when, **extremes.get(when.day, {}))

    result = climate_monthly(pd.DataFrame(rows))
    row = {item["dico"]: item for item in result.to_dict("records")}
    assert set(row) == {*bands, "0099"} and set(result["year_month"]) == {"2024-11"}
    for dico, (_, (cid, cia, p_index, s_index, w_index, tci)) in bands.items():
        got = row[dico]
        assert (got["cid"], got["cia"], got["p_index"], got["s_index"], got["w_index"]) == (
            cid, cia, p_index, s_index, w_index), dico
        assert got["tci"] == pytest.approx(tci), dico
    assert row["0001"]["precip_total"] == pytest.approx(30.0) and row["0001"]["sun_hours_mean"] == pytest.approx(9.0)

    extreme = row["0099"]
    assert (extreme["hot_days"], extreme["cold_days"], extreme["rain_days"], extreme["snow_days"]) == (3, 2, 2, 1)
    assert extreme["extreme_days"] == 7 and extreme["valid_days"] == 30
    assert extreme["extreme_days_pct"] == pytest.approx(7 / 30 * 100)


def test_us1_fr009_fr010_fr011_fr012_rent_marks_iqr_outliers_without_deleting_and_needs_ten_listings():
    def listing(number, dico, typology, rent, level="municipio", region="Norte"):
        return {"listing_id": f"L{number:03d}", "dico": dico, "dicofre": None, "locality_level": level,
                "source_region": region, "typology": typology, "asking_rent_eur": rent, "area_m2": 50.0,
                "snapshot_month": "2026-11", "license_id": "not_granted_by_source",
                "attribution": "Fonte: Idealista, extração manual; período informado pelo operador"}

    rows = [listing(i, "0101", "T2", 1000.0 + 10 * i) for i in range(12)]
    rows.append(listing(12, "0101", "T2", 5000.0))  # far above Q3 + 1.5 IQR of the T2 group
    rows += [listing(20 + i, "0101", "T1", 700.0 + 10 * i) for i in range(5)]  # only 5: no IQR, no median
    rows += [listing(40 + i, None, "T2", 900.0, level="regiao", region="Madeira") for i in range(3)]
    listings = pd.DataFrame(rows)
    municipalities = pd.DataFrame({"dico": ["0101", "0102", "3101"],
                                   "autonomous_region": [None, None, "Região Autónoma da Madeira"]})

    result = rent_stats(listings, municipalities)
    assert len(listings) == 21  # nothing is deleted from the input
    assert len(result) == 3 * 6 and set(result["typology"]) == {"ALL", "T0", "T1", "T2", "T3", "T4+"}
    row = {(item["dico"], item["typology"]): item for item in result.to_dict("records")}

    t2 = row[("0101", "T2")]
    assert (t2["n_listings"], t2["n_outliers"], t2["n_eligible"]) == (13, 1, 12)
    assert t2["rent_median"] == pytest.approx(1055.0) and t2["sample_status"] == "suficiente"
    assert t2["rent_p25"] == pytest.approx(1027.5) and t2["rent_p75"] == pytest.approx(1082.5)
    assert t2["eur_m2_median"] == pytest.approx(21.1)
    t1 = row[("0101", "T1")]  # constitution III: no median below n = 10
    assert (t1["n_listings"], t1["n_outliers"]) == (5, 0) and t1["sample_status"] == "amostra_insuficiente"
    assert pd.isna(t1["rent_median"]) and pd.isna(t1["rent_p25"]) and pd.isna(t1["rent_p75"])
    everything = row[("0101", "ALL")]  # the T2 outlier stays out of the all-typologies group too
    assert (everything["n_listings"], everything["n_outliers"], everything["n_eligible"]) == (18, 1, 17)
    assert everything["rent_median"] == pytest.approx(1030.0)
    assert everything["rent_p25"] == pytest.approx(740.0) and everything["rent_p75"] == pytest.approx(1070.0)

    coverage = {dico: row[(dico, "ALL")]["rent_coverage"] for dico in ("0101", "0102", "3101")}
    assert coverage == {"0101": "propria", "0102": "sem_anuncios", "3101": "regional_only"}
    assert row[("3101", "ALL")]["n_listings"] == 0  # regional listings are never given to a municipality
    assert result.loc[result["typology"] == "ALL", "n_listings"].sum() == 18
    assert result.loc[result["n_eligible"] < 10, "rent_median"].isna().all()


def test_us1_ac5_fr007_fr008_mobility_uses_ok_pairs_only_and_carries_google_attribution():
    municipalities = pd.DataFrame({"dico": ["0101", "1106", "3101"]})
    poles = pd.DataFrame([
        {"pole_id": "lisboa", "kind": "cidade", "routing_group": "continente", "scope": "national", "dico": "1106"},
        {"pole_id": "aeroporto_lis", "kind": "aeroporto", "routing_group": "continente", "scope": "national",
         "dico": None},
        {"pole_id": "aeroporto_fnc", "kind": "aeroporto", "routing_group": "madeira", "scope": "island",
         "dico": None},
    ])

    def pair(dico, pole_id, mode, km, minutes=None, status="ok", method=None):
        google = mode != "straight_line"
        return {"source_id": "google_distances" if google else "caop", "dico": dico, "pole_id": pole_id,
                "mode": mode, "km": km, "minutes": minutes, "status": status,
                "method": method or ("google_routes_v2" if google else "haversine"), "stale": False,
                "license_id": "not_granted_by_source" if google else "CC-BY-4.0",
                "attribution": GOOGLE_ATTRIBUTION if google else CAOP_ATTRIBUTION,
                "usage_restriction": GOOGLE_RESTRICTION if google else None,
                "reference_period": "2026-11" if google else "2025"}

    distances = pd.DataFrame([
        pair("0101", "lisboa", "straight_line", 100.0), pair("0101", "aeroporto_lis", "straight_line", 150.0),
        pair("0101", "aeroporto_fnc", "straight_line", 900.0),
        pair("1106", "lisboa", "straight_line", 0.0, method="identity"),
        pair("1106", "aeroporto_lis", "straight_line", 7.0), pair("1106", "aeroporto_fnc", "straight_line", 970.0),
        pair("3101", "lisboa", "straight_line", 960.0), pair("3101", "aeroporto_lis", "straight_line", 970.0),
        pair("3101", "aeroporto_fnc", "straight_line", 10.0),
        pair("0101", "lisboa", "driving", 110.0, 120.0), pair("0101", "aeroporto_lis", "driving", 115.0, 130.0),
        pair("1106", "lisboa", "driving", 0.0, 0.0, method="identity"),
        pair("1106", "aeroporto_lis", "driving", None, None, status="falha"),
        pair("3101", "aeroporto_fnc", "driving", 12.0, 15.0),
    ])
    criteria = catalog(
        criterion("distancia_lisboa_carro_min", {"kind": "mobility", "mode": "driving", "measure": "minutes",
                                                 "pole_id": "lisboa"}, category="distancia", weight=0.5),
        criterion("distancia_aeroporto_km", {"kind": "mobility", "mode": "straight_line", "measure": "km",
                                             "nearest_kind": "aeroporto"}, category="distancia", weight=0.0),
        criterion("distancia_aeroporto_carro_min", {"kind": "mobility", "mode": "driving", "measure": "minutes",
                                                    "nearest_kind": "aeroporto"}, category="distancia", weight=0.5),
    )
    result = mobility_indicators(distances, poles, municipalities, criteria)
    assert len(result) == 3 * 3
    row = by_key(result)

    lisbon = row[("1106", "distancia_lisboa_carro_min")]
    assert lisbon["value"] == 0.0 and lisbon["value_status"] == "observado"  # the pole itself: 0 is a value
    assert row[("0101", "distancia_lisboa_carro_min")]["value"] == pytest.approx(120.0)
    island = row[("3101", "distancia_lisboa_carro_min")]  # no route across the sea: absent, never invented
    assert pd.isna(island["value"]) and island["missing_reason"] == "sem_par_elegivel"

    nearest = {dico: row[(dico, "distancia_aeroporto_km")]["value"] for dico in ("0101", "1106", "3101")}
    assert nearest == {"0101": pytest.approx(150.0), "1106": pytest.approx(7.0), "3101": pytest.approx(10.0)}
    assert row[("0101", "distancia_aeroporto_carro_min")]["value"] == pytest.approx(130.0)
    assert row[("3101", "distancia_aeroporto_carro_min")]["value"] == pytest.approx(15.0)
    failed = row[("1106", "distancia_aeroporto_carro_min")]  # the only eligible airport pair failed
    assert pd.isna(failed["value"]) and failed["missing_reason"] == "par_falha"

    for item in result[result["value"].notna()].to_dict("records"):  # constitution III / ADR-002 D8
        if item["criterion_id"].endswith("_carro_min"):
            assert (item["license_id"], item["attribution"], item["usage_restriction"]) == (
                "not_granted_by_source", GOOGLE_ATTRIBUTION, GOOGLE_RESTRICTION)
            assert item["period"] == "2026-11"
        else:
            assert (item["license_id"], item["attribution"]) == ("CC-BY-4.0", CAOP_ATTRIBUTION)
