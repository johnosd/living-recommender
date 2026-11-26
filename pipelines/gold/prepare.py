"""Lê o lake já promovido, calcula a camada Gold e grava os parquets preparados num candidato (spec 011).

Nenhuma regra mora aqui: os cálculos estão nos módulos de `pipelines/gold/` (D2). Este módulo só lê as entradas,
junta os perfis, chama `catalog_tables` e grava `output_dir/*.parquet`, que os modelos dbt tipam e testam.
"""
from pathlib import Path

import pandas as pd
import yaml

from pipelines.gold.climate import VARIABLES, climate_indicators, climate_monthly
from pipelines.gold.common import INDICATOR_COLUMNS
from pipelines.gold.criteria import catalog_tables, load_criteria
from pipelines.gold.mobility import mobility_indicators
from pipelines.gold.observations import municipal_indicators
from pipelines.gold.parish import parish_indicators
from pipelines.gold.quality import data_quality
from pipelines.gold.rent import parish_rent_stats, rent_indicators, rent_stats

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CRITERIA = ROOT / "config/criteria.yml"
DEFAULT_SOURCES = ROOT / "config/sources.yml"
INPUTS = {
    "dim_municipality": "silver", "dim_parish": "silver", "idealista_listings": "silver",
    "census_parish_observation": "silver", "stg_observation": "bronze", "stg_climate_daily": "bronze",
    "stg_municipality_pole_distance": "bronze", "dim_mobility_pole": "bronze",
}
OBSERVATION_COLUMNS = ["source_id", "dataset_id", "dico", "period", "filter_1", "filter_2", "filter_3", "value",
                       "symbol", "license_id", "attribution"]
CLIMATE_COLUMNS = ["source_id", "dico", "variable", "date", "value", "window_start", "window_end", "license_id",
                   "attribution", "usage_restriction"]
LISTING_COLUMNS = ["listing_id", "source_id", "snapshot_month", "dico", "dicofre", "locality_level", "source_region",
                   "asking_rent_eur", "area_m2", "typology", "license_id", "attribution"]


class GoldInputError(ValueError):
    """Uma entrada do lake não existe: o build Gold depende das specs 001–009 (R-010)."""


def input_path(root: Path, table: str) -> Path:
    return Path(root) / "lake" / INPUTS[table] / table / "data.parquet"


def check_inputs(root: Path) -> None:
    missing = [f"lake/{INPUTS[table]}/{table}" for table in INPUTS if not input_path(root, table).is_file()]
    if missing:
        raise GoldInputError(f"entrada do lake ausente: {', '.join(missing)} (rode antes o build da feature dona)")


def _read(root: Path, table: str, columns: list[str] | None = None, **kwargs) -> pd.DataFrame:
    path = input_path(root, table)
    if columns is not None:
        import pyarrow.parquet as pq

        available = set(pq.read_schema(path).names)
        columns = [column for column in columns if column in available]
    return pd.read_parquet(path, columns=columns, **kwargs)


def source_restriction(source_id: str, sources_path: Path = DEFAULT_SOURCES) -> str | None:
    """`usage_restriction` declarada para a fonte em `config/sources.yml` (nula se não houver)."""
    try:
        sources = (yaml.safe_load(Path(sources_path).read_text(encoding="utf-8")) or {}).get("sources") or {}
    except OSError:
        return None
    return (sources.get(source_id) or {}).get("usage_restriction")


def _write(frame: pd.DataFrame, path: Path) -> None:
    """Colunas de texto vão como string mesmo quando inteiramente nulas (o dbt faz o `cast`)."""
    frame = frame.copy()
    for column in frame.columns:
        if frame[column].dtype == object:
            frame[column] = frame[column].astype("string")
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


def _stamp(frame: pd.DataFrame, version: str, processed_at_utc: str) -> pd.DataFrame:
    frame = frame.copy()
    if "catalog_version" not in frame.columns:
        frame["catalog_version"] = version
    frame["processed_at_utc"] = processed_at_utc
    return frame


def load_inputs(root: Path) -> dict[str, pd.DataFrame]:
    """As tabelas de entrada, só com as colunas usadas."""
    check_inputs(root)
    municipalities = _read(root, "dim_municipality", ["dico", "official_name", "autonomous_region", "area_km2"])
    return {
        "municipalities": municipalities.sort_values("dico").reset_index(drop=True),
        "parishes": _read(root, "dim_parish", ["dicofre", "dico", "area_km2"]).sort_values("dicofre")
        .reset_index(drop=True),
        "observations": _read(root, "stg_observation", OBSERVATION_COLUMNS),
        "daily": _read(root, "stg_climate_daily", CLIMATE_COLUMNS, filters=[("variable", "in", list(VARIABLES))]),
        "distances": _read(root, "stg_municipality_pole_distance"),
        "poles": _read(root, "dim_mobility_pole", ["pole_id", "kind", "routing_group", "scope", "dico"]),
        "listings": _read(root, "idealista_listings", LISTING_COLUMNS),
        "census": _read(root, "census_parish_observation"),
    }


def prepare_gold(root: Path, output_dir: Path, *, criteria_path: Path | None = None, processed_at_utc: str,
                 sources_path: Path = DEFAULT_SOURCES) -> dict:
    """Calcula a Gold e grava os parquets preparados em `output_dir`; devolve o resumo do build."""
    root, output_dir = Path(root).resolve(), Path(output_dir)
    criteria = load_criteria(Path(criteria_path) if criteria_path else DEFAULT_CRITERIA)
    data = load_inputs(root)
    municipalities = data["municipalities"]

    stats = rent_stats(data["listings"], municipalities)
    monthly = climate_monthly(data["daily"])
    restriction = source_restriction("idealista", sources_path)
    municipal = pd.concat([
        municipal_indicators(data["observations"], municipalities, criteria),
        rent_indicators(stats, municipalities, criteria, usage_restriction=restriction),
        climate_indicators(data["daily"], municipalities, criteria, monthly=monthly),
        mobility_indicators(data["distances"], data["poles"], municipalities, criteria),
    ], ignore_index=True)
    order = {item["id"]: position for position, item in enumerate(criteria["criteria"])}
    municipal = municipal.assign(_order=municipal["criterion_id"].map(order)).sort_values(
        ["_order", "variant", "dico"]).drop(columns="_order").reset_index(drop=True)

    parish_stats = parish_rent_stats(data["listings"], data["parishes"])
    parish = parish_indicators(data["parishes"], data["census"], municipal, parish_stats, criteria,
                               usage_restriction=restriction)
    order_parish = parish["criterion_id"].map(order)
    parish = parish.assign(_order=order_parish).sort_values(["_order", "variant", "dicofre"]).drop(
        columns="_order").reset_index(drop=True)

    indicators = {"municipio": municipal, "freguesia": parish}
    catalog, normalization = catalog_tables(criteria, indicators)
    version = catalog["catalog_version"].iloc[0]
    quality = data_quality(catalog, indicators, {"municipio": stats, "freguesia": parish_stats})
    tables = {
        "municipality_indicator": municipal[list(INDICATOR_COLUMNS)],
        "parish_indicator": parish,
        "rent_municipality": stats,
        "rent_parish": parish_stats,
        "climate_monthly": monthly,
        "criteria_catalog": catalog,
        "criteria_normalization": normalization,
        "data_quality": quality,
    }
    for name, frame in tables.items():
        _write(_stamp(frame, version, processed_at_utc), output_dir / f"{name}.parquet")
    statuses = catalog["status"].value_counts().to_dict()
    return {"catalog_version": version, "available": int(statuses.get("disponivel", 0)),
            "pending": catalog.loc[catalog["status"] == "fonte_pendente", "criterion_id"].tolist(),
            "rows": {name: len(frame) for name, frame in tables.items()},
            "municipalities": len(municipalities), "parishes": len(data["parishes"]), "criteria": criteria}
