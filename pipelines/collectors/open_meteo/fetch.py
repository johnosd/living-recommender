"""Cliente HTTP responsável do arquivo histórico."""
import contextlib
import json
import logging
import math
import os
import random
import tempfile
import time
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx

from pipelines.collectors._shared.datasets import QuotaExhausted
from pipelines.collectors._shared.http import (
    USER_AGENT,
    DownloadError,
    RateLimiter,
    json_content_check,
)

WAIT_SECONDS = {'minute': 61, 'hour': 3605, 'day': 86405}
MAX_WAITS = {'minute': 5, 'hour': 1}
logger = logging.getLogger(__name__)


def classify_limit(reason: str) -> str:
    reason = reason.lower()
    for word, kind in [('minute', 'minute'), ('hour', 'hour'), ('day', 'day'), ('daily', 'day')]:
        if word in reason:
            return kind
    return 'hour'


def provider_delay(headers, *, clock=time.time):
    """Prefere a espera do servidor; usa seu relógio para timestamps absolutos."""
    now = clock()
    with contextlib.suppress(ValueError, TypeError, OverflowError, KeyError):
        now = parsedate_to_datetime(headers['date']).timestamp()
    for name in ('retry-after', 'x-ratelimit-reset'):
        value = headers.get(name)
        if value is None:
            continue
        try:
            seconds = float(value)
            if name == 'x-ratelimit-reset':
                seconds -= now
        except (ValueError, TypeError, OverflowError):
            try:
                seconds = parsedate_to_datetime(value).timestamp() - now
            except (ValueError, TypeError, OverflowError):
                continue
        if math.isfinite(seconds) and seconds >= 0:
            return max(1, seconds)
    return None


def make_open_meteo_fetcher(source, *, client=None, sleep=time.sleep, wait_on_limits=True,
                          clock=time.time, jitter=random.random, max_attempts=3, on_quota=None):
    limiter = RateLimiter(source.get("limits", {}).get("min_interval_seconds", 0), sleep=sleep)

    def fetch(item, destination):
        destination = Path(destination)
        if destination.exists():
            raise FileExistsError(destination)
        params = {"latitude": item["latitude"], "longitude": item["longitude"],
                  "start_date": source["window"]["start"], "end_date": source["window"]["end"],
                  "daily": ",".join(v["id"] for v in source["variables"]),
                  "models": source["model"], "timezone": source.get("timezone", "auto")}
        last_error = None
        waits = {'minute': 0, 'hour': 0}
        with contextlib.ExitStack() as stack:
            http = client if client is not None else stack.enter_context(httpx.Client())
            attempt = 1
            while max_attempts is None or attempt <= max_attempts:
                limiter.wait()
                retry_delay = None
                try:
                    response = http.get(source["api_url"], params=params,
                                        headers={"User-Agent": USER_AGENT}, timeout=60)
                except httpx.TransportError as exc:
                    last_error = exc
                else:
                    try:
                        body = response.json()
                        reason = body.get("reason", response.text) if isinstance(body, dict) else response.text
                    except ValueError:
                        reason = response.text
                    if response.status_code == 429:
                        kind = classify_limit(str(reason))
                        supplied_delay = provider_delay(response.headers, clock=clock)
                        delay = (supplied_delay + jitter() if supplied_delay is not None else WAIT_SECONDS[kind])
                        if on_quota is not None:
                            on_quota(delay)
                        if kind == 'day' or not wait_on_limits or waits[kind] >= MAX_WAITS[kind]:
                            raise QuotaExhausted(f'cota esgotada ({kind}): {reason}')
                        waits[kind] += 1
                        sleep(delay)
                        continue
                    if response.status_code not in {408, 500, 502, 503, 504}:
                        if response.status_code >= 400:
                            raise DownloadError(f"HTTP {response.status_code}: {reason}")
                        json_content_check(response.headers.get("content-type", ""), response.content, source["api_url"])
                        try:
                            json.loads(response.content)
                        except ValueError as exc:
                            raise DownloadError("JSON inválido") from exc
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        fd, name = tempfile.mkstemp(prefix=".download-", dir=destination.parent)
                        temp = Path(name)
                        try:
                            with os.fdopen(fd, "wb") as output:
                                output.write(response.content)
                            os.link(temp, destination)
                        finally:
                            temp.unlink(missing_ok=True)
                        return {}
                    last_error = f"HTTP {response.status_code}: {reason}"
                    retry_delay = provider_delay(response.headers, clock=clock)
                if max_attempts is None or attempt < max_attempts:
                    delay = min(60, 2 ** min(attempt, 6))
                    delay = max(delay, retry_delay or 0) + jitter()
                    logger.warning('Open-Meteo: tentativa %s falhou (%s); nova tentativa em %.1f s',
                                   attempt, last_error, delay)
                    sleep(delay)
                attempt += 1
        raise DownloadError(f"falhou após {max_attempts} tentativas: {last_error}")

    return fetch
