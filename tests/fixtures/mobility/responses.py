"""Catálogo, municípios, polos e respostas sintéticas da Routes API (spec 009).

Travado junto com `tests/contracts/test_mobility_contract.py`: o executor não o edita.
Nenhuma resposta real do Google é versionada; o formato segue a documentação do método
`distanceMatrix/v2:computeRouteMatrix` (research R1). Nenhuma chave real existe aqui.
"""

import json
from datetime import UTC, datetime, timedelta

from tests.fixtures.open_meteo.responses import MemoryStorage  # noqa: F401 - reexportado para os contratos

API_URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"


def _next_tuesday_0800z(days_ahead: int = 14) -> str:
    """Sempre um dia útil futuro e dentro da janela de 90 dias que a CLI valida: o fixture nunca expira."""
    day = datetime.now(UTC) + timedelta(days=days_ahead)
    day += timedelta(days=(1 - day.weekday()) % 7)  # terça-feira
    return day.strftime("%Y-%m-%dT08:00:00Z")


TRANSIT_DEPARTURE = _next_tuesday_0800z()
KEY_SENTINEL = "fixture-key-not-real-0001-sentinel"
COLLECTED_AT = "2026-11-21T12:00:00Z"
PROCESSED_AT = "2026-11-21T13:00:00Z"

# (dico, nome, lat, lon, distrito_ou_ilha, região autónoma, grupo de roteamento)
_MUNICIPALITIES = [
    ("0101", "Alfa", 38.0, -9.0, "Distrito A", None, "continente"),
    ("0102", "Beta", 39.0, -9.0, "Distrito A", None, "continente"),
    ("0201", "Gama", 41.0, -8.0, "Distrito B", None, "continente"),
    ("3101", "Funchalense", 32.65, -16.9, "Ilha da Madeira", "Região Autónoma da Madeira", "madeira"),
    ("3102", "Portosantense", 33.07, -16.34, "Ilha de Porto Santo", "Região Autónoma da Madeira", "madeira"),
]


def municipalities() -> list[dict]:
    """Mesmo formato que `load_mobility_municipalities` devolve da dimensão CAOP."""
    return [
        {"dico": dico, "name": name, "latitude": lat, "longitude": lon,
         "district_or_island": district, "autonomous_region": region, "routing_group": group}
        for dico, name, lat, lon, district, region, group in _MUNICIPALITIES
    ]


def raw_poles() -> list[dict]:
    """Polos como escritos em `config/poles.yml`, antes de `resolve_poles`."""
    return [
        {"pole_id": "cidade_a", "name": "Cidade A", "kind": "cidade", "routing_group": "continente",
         "scope": "national", "dico": "0101"},
        {"pole_id": "aeroporto_x", "name": "Aeroporto X", "kind": "aeroporto", "routing_group": "continente",
         "scope": "national", "latitude": 38.78, "longitude": -9.13, "source_ref": "fixture"},
        {"pole_id": "sede_b", "name": "Sede B", "kind": "sede_distrito", "routing_group": "continente",
         "scope": "district", "dico": "0201"},
        {"pole_id": "funchal", "name": "Funchal", "kind": "capital_regional", "routing_group": "madeira",
         "scope": "island", "dico": "3101"},
    ]


def catalog(*, max_elements: int = 8, pricing_verified_on: str | None = "2026-11-21") -> dict:
    return {"sources": {"google_distances": {
        "id": "google_distances",
        "publisher": "Google Maps Platform",
        "responsible_party": "living-recommender",
        "license_id": "not_granted_by_source",
        "usage_restriction": "termos da Google Maps Platform; risco aceito (ADR-002 D8)",
        "attribution": "Tempos de viagem: Google",
        "risk_accepted": "ADR-002-D8-2026-11-03",
        "substitution": "OpenRouteService (carro) e GTFS da CP (comboio)",
        "collection_method": "api_json",
        "frequency": "once",
        "territorial_level": "municipality",
        "api_url": API_URL,
        "key_env": "GOOGLE_ROUTES_API_KEY",
        "reference_period": "2026-12",
        "limits": {"min_interval_seconds": 0.01, "max_attempts": 3},
        "max_elements_per_run": max_elements,
        "pricing_verified_on": pricing_verified_on,
        "pricing": {"driving": {"usd_per_1000": 5.0, "free_monthly": 10000},
                    "transit": {"usd_per_1000": 15.0, "free_monthly": 1000}},
        "modes": {
            "driving": {"travel_mode": "DRIVE", "routing_preference": "TRAFFIC_UNAWARE"},
            "transit": {"travel_mode": "TRANSIT", "departure_time": TRANSIT_DEPARTURE},
        },
    }}}


def write_catalog(path) -> None:
    import yaml

    path.write_text(yaml.safe_dump(catalog(), allow_unicode=True), encoding="utf-8")


def routes_ok(distance_m: int = 12000, seconds: int = 900) -> str:
    """Corpo de sucesso de uma matriz 1x1: lista com um elemento."""
    return json.dumps([{"originIndex": 0, "destinationIndex": 0, "distanceMeters": distance_m,
                        "duration": f"{seconds}s", "condition": "ROUTE_EXISTS"}])


def routes_not_found() -> str:
    """HTTP 200 válido: o Google respondeu que não existe rota (`sem_rota`, não falha)."""
    return json.dumps([{"originIndex": 0, "destinationIndex": 0, "condition": "ROUTE_NOT_FOUND"}])


def routes_element_error() -> str:
    """HTTP 200 cujo elemento traz erro (cota, requisição negada…): falha de coleta, não `sem_rota`."""
    return json.dumps([{"originIndex": 0, "destinationIndex": 0,
                        "status": {"code": 8, "message": "Quota exceeded for fixture"}}])


def api_error(status: str, message: str, code: int) -> str:
    return json.dumps({"error": {"code": code, "status": status, "message": message}})
