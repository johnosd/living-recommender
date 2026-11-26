"""Indicadores de clima a partir do clima diário do Open-Meteo (`stg_climate_daily`).

Regras do `weatherClassifier` legado adaptadas (extremos e TCI): `.sdd/specs/011-marts-indicadores-catalogo/
logic/clima.md`. Comparações estritas como no legado; nada é arredondado no meio do cálculo.
"""
import numpy as np
import pandas as pd

from pipelines.gold.common import available, indicator_frame, indicator_row

DATASET_ID = "stg_climate_daily"
VARIABLES = ("temperature_2m_mean", "temperature_2m_max", "temperature_2m_min", "apparent_temperature_max",
             "apparent_temperature_min", "relative_humidity_2m_mean", "precipitation_sum", "snowfall_sum",
             "sunshine_duration", "wind_speed_10m_mean")
MIN_MONTH_DAYS = 20
PROVENANCE = ("source_id", "license_id", "attribution", "usage_restriction")
EXTREMES = ("hot", "cold", "rain", "snow", "extreme")
MONTHLY_COLUMNS = ("dico", "year_month", "valid_days", "temp_mean", "temp_max_mean", "temp_min_mean",
                   "precip_total", "sun_hours_mean", "wind_mean", "humidity_mean", "hot_days", "cold_days",
                   "rain_days", "snow_days", "extreme_days", "extreme_days_pct", "cid", "cia", "p_index", "s_index",
                   "w_index", "tci", "window_start", "window_end", *PROVENANCE)
SUMMER, WINTER = (6, 7, 8), (12, 1, 2)
DAY_SHARES = {"dias_calor_pct": "hot", "dias_frio_pct": "cold", "dias_chuva_pct": "rain", "dias_neve_pct": "snow",
              "dias_extremos_pct": "extreme"}


def _days(daily: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por município x dia, com as 10 variáveis em colunas e as marcas de dia extremo."""
    data = daily[daily["variable"].isin(VARIABLES)]
    wide = data.pivot(index=["dico", "date"], columns="variable", values="value").reset_index()
    wide.columns.name = None
    for variable in VARIABLES:
        if variable not in wide.columns:
            wide[variable] = np.nan
    wide["date"] = pd.to_datetime(wide["date"])
    wide["year_month"] = wide["date"].dt.strftime("%Y-%m")
    wide["month"] = wide["date"].dt.month
    wide["valid"] = wide["temperature_2m_max"].notna()
    # NaN nunca passa numa comparação: um tipo só conta se as suas variáveis existirem no dia.
    wide["hot"] = (wide["temperature_2m_max"] > 35) | (wide["apparent_temperature_max"] > 40)
    wide["cold"] = (wide["temperature_2m_min"] < 1) | (wide["apparent_temperature_min"] < -5)
    wide["rain"] = wide["precipitation_sum"] > 35
    wide["snow"] = wide["snowfall_sum"] > 0
    wide["extreme"] = wide["hot"] | wide["cold"] | wide["rain"] | wide["snow"]
    return wide


def _meta(daily: pd.DataFrame) -> pd.DataFrame:
    """Janela e proveniência por município (as colunas que faltarem ficam nulas)."""
    frame = daily.copy()
    for column in PROVENANCE:
        if column not in frame.columns:
            frame[column] = None
    if "window_start" not in frame.columns or "window_end" not in frame.columns:
        frame["window_start"] = frame.groupby("dico")["date"].transform("min")
        frame["window_end"] = frame.groupby("dico")["date"].transform("max")
    meta = frame.groupby("dico", sort=False)[["window_start", "window_end", *PROVENANCE]].first().reset_index()
    for column in ("window_start", "window_end"):
        meta[column] = pd.to_datetime(meta[column]).dt.strftime("%Y-%m-%d")
    return meta


def _temperature_band(values: pd.Series) -> np.ndarray:
    t = values.to_numpy(dtype=float)
    return np.select([(t >= 20) & (t <= 27),
                      ((t >= 16) & (t < 20)) | ((t > 27) & (t <= 30)),
                      ((t >= 13) & (t < 16)) | ((t > 30) & (t <= 33)),
                      ((t >= 10) & (t < 13)) | ((t > 33) & (t <= 36))], [10, 7, 5, 3], 0)


def _steps(values: pd.Series, limits: tuple, compare) -> np.ndarray:
    """Pontuação em degraus 10/7/5/3/0: o primeiro limite que `compare(valor, limite)` aceita."""
    v = values.to_numpy(dtype=float)
    return np.select([compare(v, limit) for limit in limits], [10, 7, 5, 3], 0)


def climate_monthly(daily: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por município x mês (`AAAA-MM`): médias, dias extremos e TCI com os seus componentes."""
    days = _days(daily)
    grouped = days.groupby(["dico", "year_month"], sort=True)
    monthly = grouped.agg(valid_days=("valid", "sum"), temp_mean=("temperature_2m_mean", "mean"),
                          temp_max_mean=("temperature_2m_max", "mean"), temp_min_mean=("temperature_2m_min", "mean"),
                          precip_total=("precipitation_sum", "sum"), sun_seconds=("sunshine_duration", "mean"),
                          wind_mean=("wind_speed_10m_mean", "mean"), humidity_mean=("relative_humidity_2m_mean", "mean"),
                          **{f"{kind}_days": (kind, "sum") for kind in EXTREMES}).reset_index()
    monthly["sun_hours_mean"] = monthly.pop("sun_seconds") / 3600
    monthly["valid_days"] = monthly["valid_days"].astype("int64")
    for kind in EXTREMES:
        monthly[f"{kind}_days"] = monthly[f"{kind}_days"].astype("int64")
    monthly["extreme_days_pct"] = np.where(monthly["valid_days"] > 0,
                                           monthly["extreme_days"] / monthly["valid_days"].where(
                                               monthly["valid_days"] > 0) * 100, np.nan)
    # O legado usa a umidade MÉDIA no ajuste de CID e de CIA (logic/clima.md §3).
    humidity = monthly["humidity_mean"].to_numpy(dtype=float)
    adjust = np.where((humidity > 90) | (humidity < 30), -1, 0)
    components = {
        "cid": (_temperature_band(monthly["temp_mean"]) + adjust, ["temp_mean", "humidity_mean"]),
        "cia": (_temperature_band(monthly["temp_max_mean"]) + adjust, ["temp_max_mean", "humidity_mean"]),
        "p_index": (_steps(monthly["precip_total"], (30, 60, 90, 120), np.less_equal), ["precip_total"]),
        "s_index": (_steps(monthly["sun_hours_mean"], (9, 7, 5, 3), np.greater_equal), ["sun_hours_mean"]),
        "w_index": (_steps(monthly["wind_mean"], (15, 25, 35, 45), np.less), ["wind_mean"]),  # vento: estrito
    }
    short = monthly["valid_days"] < MIN_MONTH_DAYS  # mês incompleto: médias, índices e TCI nulos
    for name, (values, inputs) in components.items():
        missing = short | monthly[inputs].isna().any(axis=1)
        monthly[name] = pd.array(np.where(missing, 0, values), dtype="Int64")
        monthly.loc[missing, name] = pd.NA
    tci = (2 * monthly["cid"].astype("Float64") + 2 * monthly["cia"].astype("Float64")
           + 0.5 * monthly["p_index"].astype("Float64") + 0.5 * monthly["s_index"].astype("Float64")
           + monthly["w_index"].astype("Float64"))
    monthly["tci"] = tci.clip(lower=0, upper=100).astype("float64")
    for column in ("temp_mean", "temp_max_mean", "temp_min_mean", "precip_total", "sun_hours_mean", "wind_mean",
                   "humidity_mean", "extreme_days_pct"):
        monthly.loc[short, column] = np.nan
    monthly = monthly.merge(_meta(daily), on="dico", how="left")
    return monthly[list(MONTHLY_COLUMNS)]


def _annual(days: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    """Métricas anuais da janela por município (logic/clima.md §4)."""
    valid = days[days["valid"]]
    grouped = valid.groupby("dico")
    annual = pd.DataFrame({
        "valid_days": grouped.size(),
        "temp_media_anual": grouped["temperature_2m_mean"].mean(),
        "temp_max_anual": grouped["temperature_2m_max"].mean(),
        "temp_min_anual": grouped["temperature_2m_min"].mean(),
        "precipitacao_total": grouped["precipitation_sum"].sum(min_count=1),
        "sol_horas_dia": grouped["sunshine_duration"].mean() / 3600,
        **{metric: grouped[kind].sum() for metric, kind in DAY_SHARES.items()},
    })
    annual["precipitacao_anual"] = annual.pop("precipitacao_total") * 365.25 / annual["valid_days"]
    for metric in DAY_SHARES:
        annual[metric] = annual[metric] / annual["valid_days"] * 100
    annual["temp_max_verao"] = valid[valid["month"].isin(SUMMER)].groupby("dico")["temperature_2m_max"].mean()
    annual["temp_min_inverno"] = valid[valid["month"].isin(WINTER)].groupby("dico")["temperature_2m_min"].mean()
    annual["tci_anual"] = monthly.dropna(subset=["tci"]).groupby("dico")["tci"].mean()
    return annual


def climate_indicators(daily: pd.DataFrame, municipalities: pd.DataFrame, criteria: dict, *,
                       monthly: pd.DataFrame | None = None) -> pd.DataFrame:
    """Uma linha por município x critério disponível com `compute.kind == "climate"`.

    `monthly` (a saída de `climate_monthly`) evita recalcular o TCI quando o chamador já o tem.
    """
    items = available(criteria, "climate")
    if daily.empty:
        days = pd.DataFrame(columns=["dico", "valid", "month", *VARIABLES, *DAY_SHARES.values()])
        monthly = pd.DataFrame(columns=["dico", "tci"])
        meta = pd.DataFrame(columns=["dico", "window_start", "window_end", *PROVENANCE])
    else:
        days = _days(daily)
        monthly = climate_monthly(daily) if monthly is None else monthly
        meta = _meta(daily)
    annual = _annual(days, monthly).to_dict("index")
    info = {row["dico"]: row for row in meta.to_dict("records")}
    periods = {dico: f"{row['window_start']}/{row['window_end']}" for dico, row in info.items()}
    latest = max(periods.values()) if periods else None
    rows = []
    for criterion in items:
        metric = criterion["compute"]["metric"]
        for dico in municipalities["dico"]:
            provenance = {column: info.get(dico, {}).get(column) for column in PROVENANCE}
            value = annual.get(dico, {}).get(metric)
            value = None if value is None or pd.isna(value) else float(value)
            rows.append(indicator_row(dico, criterion, value=value, dataset_id=DATASET_ID, period=periods.get(dico),
                                      dataset_latest_period=latest,
                                      missing_reason=None if value is not None else "sem_dados_clima",
                                      **provenance))
    return indicator_frame(rows)
