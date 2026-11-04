"""Download HTTP responsável com arquivo temporário e retentativas limitadas."""

import os
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from threading import Lock

import httpx

USER_AGENT = "living-recommender/0.1 (+https://github.com/johnosd/living-recommender)"
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


class DownloadError(RuntimeError):
    """Falha ao obter um ZIP da fonte."""


class RateLimiter:
    def __init__(
        self,
        min_interval: float = 1.0,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if min_interval < 0:
            raise ValueError("min_interval deve ser não negativo")
        self.min_interval = min_interval
        self.clock = clock
        self.sleep = sleep
        self._last: float | None = None
        self._lock = Lock()

    def wait(self) -> None:
        with self._lock:
            now = self.clock()
            if self._last is not None:
                delay = self.min_interval - (now - self._last)
                if delay > 0:
                    self.sleep(delay)
            self._last = self.clock()


class HttpDownloader:
    """Instância compartilhada entre as três regiões para limitar a taxa."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        timeout: float = 30.0,
        max_attempts: int = 3,
        backoff: float = 1.0,
        rate_limiter: RateLimiter | None = None,
        sleep: Callable[[float], None] = time.sleep,
        user_agent: str = USER_AGENT,
    ):
        if timeout <= 0 or max_attempts < 1 or backoff < 0:
            raise ValueError("timeout, max_attempts ou backoff inválido")
        self.client = client
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.backoff = backoff
        self.rate_limiter = rate_limiter or RateLimiter()
        self.sleep = sleep
        self.user_agent = user_agent

    def __call__(self, url: str, destination: str | Path) -> Path:
        destination = Path(destination)
        if destination.exists():
            raise FileExistsError(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            self.rate_limiter.wait()
            fd, temp_name = tempfile.mkstemp(prefix=".download-", dir=destination.parent)
            temp = Path(temp_name)
            try:
                with os.fdopen(fd, "wb") as output:
                    if self.client is None:
                        with httpx.Client() as client:
                            self._stream(client, url, output)
                    else:
                        self._stream(self.client, url, output)
                os.link(temp, destination)
                return destination
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in RETRYABLE_STATUS:
                    break
            except Exception:
                raise
            finally:
                temp.unlink(missing_ok=True)
            if attempt < self.max_attempts:
                self.sleep(self.backoff * 2 ** (attempt - 1))
        raise DownloadError(f"download falhou após {attempt} tentativa(s): {url}: {last_error}") from last_error

    def _stream(self, client: httpx.Client, url: str, output) -> None:
        with client.stream(
            "GET", url, headers={"User-Agent": self.user_agent}, timeout=self.timeout
        ) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" in content_type:
                raise DownloadError(f"resposta HTML no lugar de GeoPackage ZIP: {url}")
            first = True
            for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                if first:
                    if not chunk.startswith(b"PK\x03\x04"):
                        raise DownloadError(f"arquivo não é ZIP/GeoPackage: {url}")
                    first = False
                output.write(chunk)
            if first:
                raise DownloadError(f"download vazio: {url}")
