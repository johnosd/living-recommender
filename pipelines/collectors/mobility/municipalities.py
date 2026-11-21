"""Municípios da dimensão CAOP, com o grupo de roteamento (spec 009, logic/pares-e-estados.md §1)."""
from pathlib import Path

import pandas as pd

from pipelines.collectors.open_meteo.municipalities import check_municipalities

COLUMNS = ["dico", "official_name", "representative_lat", "representative_lon", "district_or_island",
           "autonomous_region", "caop_version", "license_id"]


def routing_group(region) -> str:
    """Região autónoma nula é o continente; qualquer outro valor desconhecido é erro (nunca presumir)."""
    if region is None or (isinstance(region, float) and pd.isna(region)):
        return "continente"
    if "Madeira" in region:
        return "madeira"
    if "Açores" in region:
        return "acores"
    raise ValueError(f"região autónoma desconhecida: {region!r}")


def load_mobility_municipalities(silver_dir: Path) -> list[dict]:
    path = Path(silver_dir) / "dim_municipality/data.parquet"
    if not path.is_file():
        raise ValueError("Silver da CAOP ausente; execute python -m pipelines.cli.build_caop primeiro")
    frame = pd.read_parquet(path, columns=COLUMNS)
    towns = []
    for row in frame.itertuples(index=False):
        region = None if pd.isna(row.autonomous_region) else row.autonomous_region
        towns.append({
            "dico": row.dico, "name": row.official_name, "latitude": float(row.representative_lat),
            "longitude": float(row.representative_lon), "district_or_island": row.district_or_island,
            "autonomous_region": region, "routing_group": routing_group(region),
            "caop_version": None if pd.isna(row.caop_version) else str(row.caop_version),
            "license_id": None if pd.isna(row.license_id) else str(row.license_id),
        })
    check_municipalities(towns, len(towns))
    return sorted(towns, key=lambda town: town["dico"])
