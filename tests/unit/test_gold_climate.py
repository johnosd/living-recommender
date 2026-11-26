"""Indicadores anuais de clima sobre a janela coletada (spec 011, logic/clima.md §4)."""
from datetime import date, timedelta

import pandas as pd
import pytest

from pipelines.gold.climate import climate_indicators, climate_monthly

DEFAULTS = {"temperature_2m_mean": 15.0, "temperature_2m_max": 20.0, "temperature_2m_min": 10.0,
            "apparent_temperature_max": 20.0, "apparent_temperature_min": 9.0, "relative_humidity_2m_mean": 60.0,
            "precipitation_sum": 1.0, "snowfall_sum": 0.0, "sunshine_duration": 7 * 3600.0,
            "wind_speed_10m_mean": 10.0}
METRICS = ("temp_media_anual", "temp_max_anual", "temp_min_anual", "temp_max_verao", "temp_min_inverno", "precipitacao_anual", "sol_horas_dia",
           "dias_calor_pct", "tci_anual")


def days(dico, start, count, **overrides):
    rows = []
    for offset in range(count):
        when = start + timedelta(days=offset)
        values = {**DEFAULTS, **overrides}
        if when.month in (6, 7, 8):
            values["temperature_2m_max"] = 30.0
        if when.month in (12, 1, 2):
            values["temperature_2m_min"] = 2.0
        for variable, value in values.items():
            rows.append({"source_id": "open_meteo", "dico": dico, "variable": variable, "date": when, "value": value,
                         "window_start": date(2024, 6, 1), "window_end": date(2025, 2, 28),
                         "license_id": "CC-BY-4.0", "attribution": "Open-Meteo", "usage_restriction": "nc"})
    return rows


def catalog():
    return {"criteria": [{"id": f"clima_{metric}", "category": "clima", "unit": "u", "levels": ["municipio"],
                          "status": "disponivel", "compute": {"kind": "climate", "metric": metric}}
                         for metric in METRICS]}


@pytest.fixture(scope="module")
def result():
    daily = pd.DataFrame(days("0101", date(2024, 6, 1), 273))  # 2024-06-01 a 2025-02-28
    daily = pd.concat([daily, pd.DataFrame(days("0102", date(2024, 6, 1), 10))])  # só 10 dias: sem TCI
    towns = pd.DataFrame({"dico": ["0101", "0102", "0103"]})
    frame = climate_indicators(daily, towns, catalog())
    return {(row["dico"], row["criterion_id"]): row for row in frame.to_dict("records")}, daily


def test_summer_winter_and_annualized_precipitation(result):
    rows, _ = result
    assert rows[("0101", "clima_temp_max_verao")]["value"] == pytest.approx(30.0)
    assert rows[("0101", "clima_temp_min_inverno")]["value"] == pytest.approx(2.0)
    assert rows[("0101", "clima_precipitacao_anual")]["value"] == pytest.approx(365.25)
    assert rows[("0101", "clima_sol_horas_dia")]["value"] == pytest.approx(7.0)
    assert rows[("0101", "clima_temp_media_anual")]["value"] == pytest.approx(15.0)
    # FR-014: máxima e mínima médias do ano inteiro (92 dias de verão a 30 °C e 181 a 20 °C; 90 de inverno a 2 °C)
    assert rows[("0101", "clima_temp_max_anual")]["value"] == pytest.approx((92 * 30.0 + 181 * 20.0) / 273)
    assert rows[("0101", "clima_temp_min_anual")]["value"] == pytest.approx((90 * 2.0 + 183 * 10.0) / 273)
    assert rows[("0101", "clima_dias_calor_pct")]["value"] == 0.0
    period = rows[("0101", "clima_tci_anual")]
    assert period["period"] == "2024-06-01/2025-02-28" and period["dataset_id"] == "stg_climate_daily"
    assert (period["license_id"], period["usage_restriction"]) == ("CC-BY-4.0", "nc")


def test_tci_annual_is_the_mean_of_complete_months_only(result):
    rows, daily = result
    monthly = climate_monthly(daily)
    complete = monthly[(monthly["dico"] == "0101") & monthly["tci"].notna()]
    assert len(complete) == 9
    assert rows[("0101", "clima_tci_anual")]["value"] == pytest.approx(complete["tci"].mean())
    short = monthly[monthly["dico"] == "0102"].iloc[0]
    assert short["valid_days"] == 10 and pd.isna(short["tci"]) and pd.isna(short["cid"])
    tci = rows[("0102", "clima_tci_anual")]
    assert pd.isna(tci["value"]) and tci["missing_reason"] == "sem_dados_clima"


def test_municipality_without_days_is_absent_with_reason(result):
    rows, _ = result
    for metric in METRICS:
        row = rows[("0103", f"clima_{metric}")]
        assert pd.isna(row["value"]) and row["missing_reason"] == "sem_dados_clima"
