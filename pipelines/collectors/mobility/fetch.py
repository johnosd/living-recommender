"""Cliente HTTP da Routes API `computeRouteMatrix`, uma requisição 1x1 por par (spec 009, research R1/R3)."""
import contextlib
import json
import os
import random
import tempfile
import time
from pathlib import Path

import httpx

from pipelines.collectors._shared.datasets import QuotaExhausted, StopCollection
from pipelines.collectors._shared.http import (
    USER_AGENT,
    DownloadError,
    RateLimiter,
    json_content_check,
)
from pipelines.collectors.mobility.catalog import FIELD_MASK
from pipelines.collectors.mobility.secrets import redact
from pipelines.collectors.open_meteo.fetch import provider_delay

RETRYABLE = {408, 500, 502, 503, 504}


class AuthorizationStop(StopCollection):
    """Chave recusada ou sem permissão: a coleta para; o resto fica `pending` e nada é cobrado à toa."""


def request_body(item: dict) -> dict:
    def waypoint(lat, lon):
        return {"waypoint": {"location": {"latLng": {"latitude": lat, "longitude": lon}}}}

    body = {"origins": [waypoint(item["origin_lat"], item["origin_lon"])],
            "destinations": [waypoint(item["dest_lat"], item["dest_lon"])], "travelMode": item["travel_mode"]}
    if item.get("routing_preference"):
        body["routingPreference"] = item["routing_preference"]
    if item.get("departure_time"):
        body["departureTime"] = item["departure_time"]
    return body


def _reason(response: httpx.Response, api_key: str) -> str:
    try:
        document = response.json()
    except ValueError:
        document = None
    error = document.get("error") if isinstance(document, dict) else None
    text = f"{error.get('status')}: {error.get('message')}" if isinstance(error, dict) else response.text[:300]
    return redact(text, api_key)


def make_routes_fetcher(source: dict, *, api_key: str, client=None, sleep=time.sleep, on_quota=None,
                        jitter=random.random, clock=time.time):
    """`fetch(item, destination)`: grava só uma resposta HTTP 200 JSON; 401/403 e cota param a coleta."""
    limiter = RateLimiter(source["limits"]["min_interval_seconds"], sleep=sleep)
    max_attempts = source["limits"]["max_attempts"]
    headers = {"User-Agent": USER_AGENT, "X-Goog-Api-Key": api_key, "X-Goog-FieldMask": FIELD_MASK}

    def fetch(item, destination):
        destination = Path(destination)
        if destination.exists():
            raise FileExistsError(destination)
        last_error = "sem resposta"
        with contextlib.ExitStack() as stack:
            http = client if client is not None else stack.enter_context(httpx.Client())
            for attempt in range(1, max_attempts + 1):
                limiter.wait()
                retry_delay = None
                try:
                    response = http.post(source["api_url"], json=request_body(item), headers=headers, timeout=60)
                except httpx.TransportError as exc:
                    last_error = redact(f"{type(exc).__name__}: {exc}", api_key)
                else:
                    status = response.status_code
                    if status in (401, 403):
                        raise AuthorizationStop(f"autorização recusada (HTTP {status}): {_reason(response, api_key)}")
                    if status == 429:
                        if on_quota is not None:
                            on_quota(provider_delay(response.headers, clock=clock))
                        raise QuotaExhausted(f"cota esgotada (HTTP 429): {_reason(response, api_key)}")
                    if status in RETRYABLE:
                        last_error = f"HTTP {status}: {_reason(response, api_key)}"
                        retry_delay = provider_delay(response.headers, clock=clock)
                    elif status >= 400:
                        raise DownloadError(f"HTTP {status}: {_reason(response, api_key)}")
                    else:
                        json_content_check(response.headers.get("content-type", ""), response.content,
                                           source["api_url"])
                        try:
                            json.loads(response.content)
                        except ValueError as exc:
                            raise DownloadError("JSON inválido") from exc
                        _write_atomically(destination, response.content)
                        return {}
                if attempt < max_attempts:
                    sleep(max(min(60, 2 ** min(attempt, 6)), retry_delay or 0) + jitter())
        raise DownloadError(f"falhou após {max_attempts} tentativas: {last_error}")

    return fetch


def _write_atomically(destination: Path, content: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".download-", dir=destination.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(content)
        os.link(temp, destination)
    finally:
        temp.unlink(missing_ok=True)
