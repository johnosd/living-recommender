"""Configuração restrita à API oficial de leitura aprovada em 008/R-001."""

from copy import deepcopy
from math import isfinite
from urllib.parse import urlsplit

from pipelines.collectors._shared.http import USER_AGENT

API_URL = "https://pt.wikipedia.org/w/api.php"
ROBOTS_EXCEPTION = "008-R-001-authorized-2026-11-20"


def validate_contact(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("contato identificável obrigatório")
    url = urlsplit(value)
    if not ((url.scheme == "https" and url.hostname and not url.username)
            or ("@" in value and " " not in value)):
        raise ValueError("contato deve ser URL HTTPS ou email")
    return value


def wikipedia_source(catalog):
    source = deepcopy(catalog["sources"]["wikipedia"])
    expected = {"id": "wikipedia", "language": "pt", "api_url": API_URL,
                "collection_method": "api_json", "territorial_level": "municipality",
                "license_id": "CC-BY-SA-4.0", "robots_exception": ROBOTS_EXCEPTION}
    for field, value in expected.items():
        if source.get(field) != value:
            raise ValueError(f"catálogo Wikipedia inválido: {field}")
    for field in ("publisher", "responsible_party", "frequency", "license_url", "attribution"):
        if not source.get(field):
            raise ValueError(f"catálogo sem {field}")
    if type(source.get("expected_municipalities")) is not int or source["expected_municipalities"] < 1:
        raise ValueError("universo esperado inválido")
    interval = float(source.get("min_interval_seconds", 0))
    if not isfinite(interval) or interval < 1 or source.get("maxlag") != 5:
        raise ValueError("taxa mínima 1 segundo; maxlag obrigatório 5")
    if not str(source["license_url"]).startswith("https://creativecommons.org/licenses/by-sa/4.0/"):
        raise ValueError("URL de licença divergente")
    if type(source.get("max_attempts", 3)) is not int or not 1 <= source.get("max_attempts", 3) <= 3:
        raise ValueError("max_attempts deve estar entre 1 e 3")
    timeout = float(source.get("timeout_seconds", 30))
    if not isfinite(timeout) or not 0 < timeout <= 30:
        raise ValueError("timeout deve estar entre 0 e 30 segundos")
    # O contato público do projeto é default também nas interfaces injetáveis.
    validate_contact(source.get("contact", "https://github.com/johnosd/living-recommender"))
    if not source.get("user_agent", USER_AGENT).startswith("living-recommender/"):
        raise ValueError("User-Agent deve identificar living-recommender")
    return source
