"""Pontos representativos da dimensão territorial Silver."""
import math
import re
from pathlib import Path

import pandas as pd


def load_climate_municipalities(silver_dir: Path) -> list[dict]:
    path = Path(silver_dir) / "dim_municipality/data.parquet"
    if not path.is_file():
        raise ValueError("Silver da CAOP ausente; execute python -m pipelines.cli.build_caop primeiro")
    frame = pd.read_parquet(path, columns=["dico", "official_name", "representative_lat", "representative_lon"])
    return frame.rename(columns={"official_name": "name", "representative_lat": "latitude",
                                 "representative_lon": "longitude"}).to_dict("records")


def check_municipalities(towns, expected: int) -> None:
    if len(towns) != expected:
        raise ValueError(f"municípios: esperados {expected}, recebidos {len(towns)}")
    seen = set()
    for town in towns:
        dico = town.get("dico")
        if not isinstance(dico, str) or not re.fullmatch(r"[0-9]{4}", dico):
            raise ValueError(f"dico inválido: {dico}")
        if dico in seen:
            raise ValueError(f"dico repetido: {dico}")
        seen.add(dico)
        for key, low, high in [("latitude", 29, 43), ("longitude", -32, -6)]:
            value = town.get(key)
            if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{dico}: {key} ausente ou fora de Portugal: {value}")
