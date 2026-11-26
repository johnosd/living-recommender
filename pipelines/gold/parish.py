"""Perfil de freguesia com origem sinalizada: `proprio`, `herdado` (cópia exata do município) ou `ausente`.

Regras: `.sdd/specs/011-marts-indicadores-catalogo/data-model.md` (`gold_parish_indicator`), D9 e FR-029/FR-030.
Valor próprio só onde o critério tem `compute_parish` (Censos 2021 ou aluguel da freguesia). `origin_level` diz o
nível de onde veio o valor (spec 012, `logic/heranca.md` §8): a cadeia do aluguel chega aqui pelo município.
"""
import numpy as np
import pandas as pd

from pipelines.gold.common import (
    INDICATOR_COLUMNS,
    ORIGIN_COLUMNS,
    indicator_frame,
    indicator_row,
)
from pipelines.gold.rent import rent_rows

KEY = ["dicofre", "criterion_id", "variant"]
VALUE_COLUMNS = [column for column in INDICATOR_COLUMNS if column not in ("dico", "criterion_id", "category",
                                                                         "variant")]
PARISH_COLUMNS = ("dicofre", "dico", *[column for column in INDICATOR_COLUMNS if column != "dico"], *ORIGIN_COLUMNS,
                  "territorial_inheritance")
CENSUS_SOURCE = "censos"
CENSUS_DATASET = "census_parish_observation"
CENSUS_GROUPS = {"pct_25_39": ("25_29", "30_34", "35_39"),
                 "pct_65_mais": ("65_69", "70_74", "75_79", "80_84", "85_plus")}


def _census_value(codes: dict, metric: str, area) -> float | None:
    total = codes.get("T")
    if total is None or pd.isna(total):
        return None
    if metric == "residentes":
        return float(total)
    if metric == "densidade":
        return float(total) / float(area) if area is not None and not pd.isna(area) and area > 0 else None
    parts = [codes.get(code) for code in CENSUS_GROUPS[metric]]
    if total == 0 or any(part is None or pd.isna(part) for part in parts):
        return None
    return sum(float(part) for part in parts) / float(total) * 100


def census_rows(parishes: pd.DataFrame, census: pd.DataFrame, items: list[tuple[dict, dict]]) -> list[dict]:
    """Linhas próprias dos critérios `census` (Censos 2021 por freguesia, área da CAOP)."""
    if not items:
        return []
    by_parish: dict[str, dict] = {}
    meta: dict[str, dict] = {}
    for row in census.to_dict("records"):
        by_parish.setdefault(row["dicofre"], {})[row["age_code"]] = row["value"]
        meta.setdefault(row["dicofre"], row)
    output = []
    for criterion, compute in items:
        for dicofre, area in zip(parishes["dicofre"], parishes["area_km2"], strict=True):
            info = meta.get(dicofre, {})
            value = _census_value(by_parish.get(dicofre, {}), compute["metric"], area)
            period = None if info.get("period") is None else str(info.get("period"))
            output.append(indicator_row(
                dicofre, criterion, value=value, period=period, dataset_latest_period=period,
                source_id=CENSUS_SOURCE, dataset_id=CENSUS_DATASET, license_id=info.get("license_id"),
                attribution=info.get("attribution"), missing_reason=None if value is not None else "sem_publicacao",
                territorial_inheritance=info.get("coverage_status")))
    return output


def parish_indicators(parishes: pd.DataFrame, census: pd.DataFrame, municipal_indicators: pd.DataFrame,
                      parish_rent: pd.DataFrame, criteria: dict, *, usage_restriction: str | None = None
                      ) -> pd.DataFrame:
    """Uma linha por freguesia × critério disponível × variante, com `origin` e a herança territorial dos Censos."""
    available = {item["id"] for item in criteria["criteria"] if item.get("status") == "disponivel"}
    municipal = municipal_indicators[municipal_indicators["criterion_id"].isin(available)]
    base = parishes[["dicofre", "dico"]].merge(municipal, on="dico", how="inner")
    inherited = base["value"].notna()
    # O nível do herdado é o de onde o município tirou o valor; sem a coluna, é o próprio município.
    levels = base["origin_level"] if "origin_level" in base.columns else pd.Series("municipio", index=base.index)
    base["origin"] = np.where(inherited, "herdado", "ausente")  # sobrescreve a origem do município
    base["origin_level"] = levels.astype(object).where(inherited, None)
    base["territorial_inheritance"] = None

    own_items = [(item, item["compute_parish"]) for item in criteria["criteria"]
                 if item.get("status") == "disponivel" and item.get("compute_parish")]
    census_items = [pair for pair in own_items if pair[1]["kind"] == "census"]
    rent_items = [pair for pair in own_items if pair[1]["kind"] == "rent"]
    own_rows = census_rows(parishes, census, census_items)
    if rent_items and not parish_rent.empty:
        own_rows += rent_rows(parish_rent, "dicofre", rent_items, usage_restriction=usage_restriction)
    if not own_rows:
        frame = base
    else:
        inheritance = {(row["dico"], row["criterion_id"]): row.get("territorial_inheritance") for row in own_rows}
        own = indicator_frame(own_rows).rename(columns={"dico": "dicofre"})
        own["territorial_inheritance"] = [inheritance.get((d, c)) for d, c in zip(own["dicofre"],
                                                                                  own["criterion_id"], strict=True)]
        own = own.merge(parishes[["dicofre", "dico"]], on="dicofre", how="inner")
        frame = _combine(base, own)
    frame = frame.sort_values(KEY).reset_index(drop=True)
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce").astype("float64")
    frame["is_older_period"] = frame["is_older_period"].fillna(False).astype(bool)
    frame["is_stale"] = frame["is_stale"].fillna(False).astype(bool)
    return frame[list(PARISH_COLUMNS)]


def _combine(base: pd.DataFrame, own: pd.DataFrame) -> pd.DataFrame:
    """Valor próprio vence; sem valor próprio, fica o herdado do município; sem nenhum, ausente com o motivo próprio."""
    base = base.set_index(KEY)
    own = own.set_index(KEY)
    extra = own.index.difference(base.index)
    if len(extra):  # variante só da freguesia: começa ausente
        added = own.loc[extra].copy()
        added[["value", "missing_reason"]] = [None, "sem_publicacao"]
        added["origin"] = "ausente"
        added["origin_level"] = None
        base = pd.concat([base, added[base.columns]])
    has_value = own["value"].notna()
    valued = own[has_value].index
    base.loc[valued, VALUE_COLUMNS] = own.loc[valued, VALUE_COLUMNS].to_numpy()
    base.loc[valued, "origin"] = "proprio"
    base.loc[valued, "origin_level"] = "freguesia"
    absent = own[~has_value].index
    still_absent = absent[base.loc[absent, "value"].isna().to_numpy()]
    base.loc[still_absent, VALUE_COLUMNS] = own.loc[still_absent, VALUE_COLUMNS].to_numpy()
    base.loc[still_absent, "origin"] = "ausente"
    base.loc[still_absent, "origin_level"] = None
    census_index = own.index[own["territorial_inheritance"].notna()]
    base.loc[census_index, "territorial_inheritance"] = own.loc[census_index, "territorial_inheritance"].to_numpy()
    return base.reset_index()
