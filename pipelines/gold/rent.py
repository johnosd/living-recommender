"""Aluguel descritivo do Idealista por território e tipologia, com outliers marcados por IQR.

Regras: `.sdd/specs/011-marts-indicadores-catalogo/logic/aluguel.md`. A marca de outlier existe só em memória:
nenhuma linha por anúncio sai deste módulo (constitution IV e VI).
"""
import numpy as np
import pandas as pd

from pipelines.gold.common import (
    MIN_SAMPLE,
    TYPOLOGIES,
    available,
    indicator_frame,
    indicator_row,
)

SOURCE_ID = "idealista"
DATASET_ID = "idealista_listings"
AREA_RANGE = (10.0, 1000.0)  # plano §7.3: fora disso o €/m² não é confiável
IQR_FACTOR = 1.5
REGIONS = {"Região Autónoma da Madeira": "Madeira", "Região Autónoma dos Açores": "Açores"}
STATS_COLUMNS = ("typology", "n_listings", "n_outliers", "n_eligible", "rent_median", "rent_p25", "rent_p75",
                 "n_eur_m2", "eur_m2_median", "sample_status", "rent_coverage", "snapshot_month", "source_id",
                 "license_id", "attribution")
METRICS = {"median": ("rent_median", "n_eligible"), "eur_m2_median": ("eur_m2_median", "n_eur_m2")}


def _current(listings: pd.DataFrame) -> pd.DataFrame:
    """Snapshot vigente (o `snapshot_month` mais recente), só com preço válido."""
    if listings.empty:
        return listings.assign(outlier=pd.Series(dtype=bool))
    latest = listings["snapshot_month"].max()
    current = listings[(listings["snapshot_month"] == latest) & listings["asking_rent_eur"].notna()].copy()
    current["outlier"] = _outliers(current)
    return current


def _outliers(listings: pd.DataFrame, key: str = "dico") -> pd.Series:
    """IQR de Tukey por território (`key`) x tipologia, só em grupos com pelo menos 10 preços (D6).

    O padrão é o município; o distrito e a região da spec 012 passam a sua própria coluna.
    """
    flags = pd.Series(False, index=listings.index)
    placed = listings[listings[key].notna() & listings["typology"].notna()]
    for _, group in placed.groupby([key, "typology"], sort=False):
        if len(group) < MIN_SAMPLE:
            continue
        prices = group["asking_rent_eur"].astype(float)
        q1, q3 = np.percentile(prices.to_numpy(), [25, 75])
        spread = IQR_FACTOR * (q3 - q1)
        flags.loc[group.index] = (prices < q1 - spread) | (prices > q3 + spread)
    return flags


def _stats(group: pd.DataFrame) -> dict:
    eligible = group[~group["outlier"]]
    prices = eligible["asking_rent_eur"].astype(float).to_numpy()
    area = eligible["area_m2"].astype(float)
    in_range = eligible[area.between(*AREA_RANGE)]
    eur_m2 = (in_range["asking_rent_eur"].astype(float) / in_range["area_m2"].astype(float)).to_numpy()
    row = {"n_listings": len(group), "n_outliers": int(group["outlier"].sum()), "n_eligible": len(prices),
           "rent_median": None, "rent_p25": None, "rent_p75": None, "n_eur_m2": len(eur_m2),
           "eur_m2_median": None}
    if len(prices) >= MIN_SAMPLE:  # constitution III: nenhuma mediana abaixo de 10 anúncios
        p25, p50, p75 = np.percentile(prices, [25, 50, 75])
        row.update(rent_median=float(p50), rent_p25=float(p25), rent_p75=float(p75))
    if len(eur_m2) >= MIN_SAMPLE:
        row["eur_m2_median"] = float(np.median(eur_m2))
    row["sample_status"] = ("suficiente" if len(prices) >= MIN_SAMPLE
                            else "amostra_insuficiente" if len(prices) else "sem_anuncios")
    return row


def _territory_rows(listings: pd.DataFrame, key: str, territory: str) -> list[dict]:
    rows = []
    for typology in TYPOLOGIES:
        group = listings if typology == "ALL" else listings[listings["typology"] == typology]
        rows.append({key: territory, "typology": typology, **_stats(group)})
    return rows


def _coverage(n_eligible: int) -> str:
    return "propria" if n_eligible >= MIN_SAMPLE else "insuficiente" if n_eligible else "sem_anuncios"


def _provenance(current: pd.DataFrame) -> dict:
    if current.empty:
        return {"snapshot_month": None, "source_id": SOURCE_ID, "license_id": None, "attribution": None}
    first = current.iloc[0]
    return {"snapshot_month": first["snapshot_month"], "source_id": SOURCE_ID, "license_id": first.get("license_id"),
            "attribution": first.get("attribution")}


def _frame(rows: list[dict], key_columns: list[str], columns: tuple = STATS_COLUMNS) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=[*key_columns, *columns])
    for column in ("rent_median", "rent_p25", "rent_p75", "eur_m2_median"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("float64")
    for column in ("n_listings", "n_outliers", "n_eligible", "n_eur_m2"):
        frame[column] = frame[column].astype("int64")
    return frame


def rent_stats(listings: pd.DataFrame, municipalities: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por município x tipologia (`ALL`, `T0`...`T4+`), inclusive municípios sem anúncios."""
    current = _current(listings)
    provenance = _provenance(current)
    municipal = current[current["dico"].notna()]
    by_dico = {dico: group for dico, group in municipal.groupby("dico", sort=False)}
    regional = set(current.loc[current["dico"].isna(), "source_region"].dropna()) if not current.empty else set()
    regions = municipalities["autonomous_region"] if "autonomous_region" in municipalities.columns else None
    rows = []
    for position, dico in enumerate(municipalities["dico"]):
        group = by_dico.get(dico, current.iloc[0:0])
        territory = _territory_rows(group, "dico", dico)
        eligible = territory[0]["n_eligible"]
        coverage = _coverage(eligible)
        region = None if regions is None else regions.iloc[position]
        if coverage == "sem_anuncios" and isinstance(region, str) and REGIONS.get(region) in regional:
            coverage = "regional_only"  # há anúncios só com a região: nunca atribuídos a um município
        for row in territory:
            row.update(rent_coverage=coverage, **provenance)
        rows.extend(territory)
    return _frame(rows, ["dico"])


def parish_rent_stats(listings: pd.DataFrame, parishes: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por freguesia x tipologia, com os outliers marcados no grupo município x tipologia."""
    current = _current(listings)  # a marca vem do grupo municipal (logic/aluguel.md §4)
    provenance = _provenance(current)
    located = current[current["dicofre"].notna()] if not current.empty else current
    by_parish = {dicofre: group for dicofre, group in located.groupby("dicofre", sort=False)}
    rows = []
    for dicofre, dico in zip(parishes["dicofre"], parishes["dico"], strict=True):
        territory = _territory_rows(by_parish.get(dicofre, current.iloc[0:0]), "dicofre", dicofre)
        coverage = _coverage(territory[0]["n_eligible"])
        for row in territory:
            row.update(dico=dico, rent_coverage=coverage, **provenance)
        rows.extend(territory)
    return _frame(rows, ["dicofre", "dico"])


def _absence(row: dict, count_column: str) -> str:
    if row["rent_coverage"] == "regional_only":
        return "regional_only"
    if row["n_eligible"] == 0:
        return "sem_anuncios"
    return "amostra_insuficiente" if row[count_column] < MIN_SAMPLE else "sem_anuncios"


def rent_rows(stats: pd.DataFrame, key: str, items: list[tuple[dict, dict]], *,
              usage_restriction: str | None = None) -> list[dict]:
    """Linhas de indicador de `custo_*` a partir das estatísticas (`logic/aluguel.md` §5).

    `items` traz `(critério, compute)`: o `compute` do município ou o `compute_parish` da freguesia.
    """
    indexed = {(row[key], row["typology"]): row for row in stats.to_dict("records")}
    territories = list(dict.fromkeys(stats[key]))
    output = []
    for criterion, compute in items:
        value_column, count_column = METRICS[compute["metric"]]
        for territory in territories:
            for variant in compute["variants"]:
                row = indexed[(territory, variant)]
                value = row[value_column]
                value = None if value is None or pd.isna(value) else float(value)
                period = row["snapshot_month"]
                extra = {"variant": variant, "period": period, "dataset_latest_period": period,
                         "source_id": SOURCE_ID, "dataset_id": DATASET_ID, "license_id": row["license_id"],
                         "attribution": row["attribution"], "usage_restriction": usage_restriction,
                         "missing_reason": None if value is not None else _absence(row, count_column)}
                output.append(indicator_row(territory, criterion, value=value, **extra))
    return output


def rent_indicators(stats: pd.DataFrame, municipalities: pd.DataFrame, criteria: dict, *,
                    usage_restriction: str | None = None) -> pd.DataFrame:
    """Linhas de `custo_aluguel_mediana` (por variante) e `custo_aluguel_m2` no município."""
    wanted = set(municipalities["dico"])
    stats = stats[stats["dico"].isin(wanted)]
    items = [(criterion, criterion["compute"]) for criterion in available(criteria, "rent")]
    return indicator_frame(rent_rows(stats, "dico", items, usage_restriction=usage_restriction))
