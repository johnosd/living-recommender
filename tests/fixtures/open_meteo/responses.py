"""Respostas sintéticas da API de arquivo do Open-Meteo, catálogo e armazenamento em memória (spec 003).

Travado junto com `tests/contracts/test_climate_collection_contract.py`: o executor não o edita.
Nenhuma resposta real é versionada; o formato foi conferido numa sondagem de 2026-11-11 (research R1).
"""

import json
from datetime import date, timedelta

VARIABLES = {
    "temperature_2m_mean": "°C",
    "temperature_2m_max": "°C",
    "temperature_2m_min": "°C",
    "apparent_temperature_mean": "°C",
    "apparent_temperature_max": "°C",
    "apparent_temperature_min": "°C",
    "precipitation_sum": "mm",
    "snowfall_sum": "cm",
    "sunshine_duration": "s",
    "wind_speed_10m_mean": "km/h",
    "wind_speed_10m_max": "km/h",
    "wind_gusts_10m_max": "km/h",
    "relative_humidity_2m_mean": "%",
}
START, END = "2025-01-01", "2025-01-05"
MINUTE_LIMIT = "Minutely API request limit exceeded. Please try again in one minute."
HOUR_LIMIT = "Hourly API request limit exceeded. Please try again in the next hour."
DAY_LIMIT = "Daily API request limit exceeded. Please try again tomorrow."


def days(start: str = START, end: str = END) -> list[str]:
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    return [(first + timedelta(days=offset)).isoformat() for offset in range((last - first).days + 1)]


def open_meteo_response(
    *, start: str = START, end: str = END, latitude: float = 38.75, longitude: float = -9.25,
    elevation: float = 64.0, timezone: str = "Europe/Lisbon", utc_offset_seconds: int = 0,
    generation_ms: float = 0.2, nulls: dict[str, set[int] | str] | None = None,
    drop: tuple[str, ...] = (), short_by: int = 0,
) -> str:
    """Corpo JSON no formato do arquivo diário.

    ``nulls``: ``{variável: {índices dos dias}}`` ou ``{variável: "all"}``; ``drop``: variáveis omitidas;
    ``short_by``: dias a menos no fim da série.
    """
    nulls = nulls or {}
    times = days(start, end)
    if short_by:
        times = times[:-short_by]
    kept = {name: unit for name, unit in VARIABLES.items() if name not in drop}
    daily: dict[str, list] = {"time": times}
    for position, name in enumerate(kept):
        marked = nulls.get(name, set())
        values = []
        for index in range(len(times)):
            if marked == "all" or index in marked:
                values.append(None)
            elif name == "relative_humidity_2m_mean":
                values.append(60 + index % 30)
            else:
                values.append(round(5 + position + index * 0.1, 1))
        daily[name] = values
    document = {
        "latitude": latitude, "longitude": longitude, "generationtime_ms": generation_ms,
        "utc_offset_seconds": utc_offset_seconds, "timezone": timezone, "timezone_abbreviation": "GMT",
        "elevation": elevation, "daily_units": {"time": "iso8601", **kept}, "daily": daily,
    }
    return json.dumps(document, ensure_ascii=False, separators=(",", ":"))


def error_response(reason: str) -> str:
    return json.dumps({"error": True, "reason": reason})


def municipalities(count: int) -> list[dict]:
    """Municípios sintéticos no formato que o handler recebe da dimensão da spec 001."""
    return [
        {"dico": f"{number:04d}", "name": f"Município {number:04d}",
         "latitude": 37.0 + number * 0.01, "longitude": -8.0 - number * 0.01}
        for number in range(1, count + 1)
    ]


def catalog(count: int, *, start: str = START, end: str = END) -> dict:
    """Catálogo mínimo da fonte `open_meteo`, com ``expected_municipalities`` igual a ``count``."""
    return {"open_meteo": {
        "id": "open_meteo", "license_id": "CC-BY-4.0", "collection_method": "api_json",
        "attribution": "Dados meteorológicos: Open-Meteo.com (CC BY 4.0)",
        "api_url": "https://archive-api.open-meteo.com/v1/archive",
        "model": "era5", "timezone": "auto", "window": {"start": start, "end": end},
        "expected_municipalities": count,
        "variables": [{"id": name, "unit": unit} for name, unit in VARIABLES.items()],
    }}


class MemoryStorage:
    """Mesma interface mínima do `LocalStorage`; recusa sobrescrever (constitution V)."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key, content):
        if key in self.objects:
            raise AssertionError(f"overwrite: {key}")
        self.objects[key] = content

    def put_file(self, key, path):
        self.put(key, path.read_bytes())

    def get(self, key):
        return self.objects[key]

    def delete(self, key):
        self.objects.pop(key, None)

    def list_keys(self, prefix: str = ""):
        return {key for key in self.objects if key.startswith(prefix)}
