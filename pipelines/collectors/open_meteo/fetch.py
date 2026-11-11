"""Cliente HTTP responsável do arquivo histórico."""
import contextlib
import json
import os
import tempfile
import time
from pathlib import Path

import httpx

from pipelines.collectors._shared.http import (
    USER_AGENT,
    DownloadError,
    RateLimiter,
    json_content_check,
)


def make_open_meteo_fetcher(source, *, client=None, sleep=time.sleep, wait_on_limits=True):
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
        with contextlib.ExitStack() as stack:
            http = client if client is not None else stack.enter_context(httpx.Client())
            for attempt in range(1, 4):
                limiter.wait()
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
                if attempt < 3:
                    sleep(2 ** attempt)
        raise DownloadError(f"falhou após 3 tentativas: {last_error}")

    return fetch
