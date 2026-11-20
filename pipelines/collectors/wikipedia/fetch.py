"""HTTP serial identificado; nenhuma navegação para URLs contidas nos artigos."""

import time
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

import httpx

from pipelines.collectors._shared.http import USER_AGENT, RateLimiter
from pipelines.collectors.wikipedia.catalog import API_URL, validate_contact
from pipelines.collectors.wikipedia.manifest import encode


class FetchError(ValueError):
    pass


class SourceBlocked(FetchError):
    """Interrompe a fonte inteira; não trocar endpoint ou identidade."""


class PendingFetch(FetchError):
    def __init__(self, message, retry_at=None):
        super().__init__(message)
        self.retry_at = retry_at


class WikipediaFetcher:
    def __init__(self, source, *, client=None, sleep=time.sleep, clock=time.monotonic,
                 now=lambda: datetime.now(UTC), cancelled=lambda: False):
        self.source = source
        validate_contact(source.get("contact", "https://github.com/johnosd/living-recommender"))
        self.client = client or httpx.Client(timeout=min(float(source.get("timeout_seconds", 30)), 30),
                                             follow_redirects=False)
        self.sleep, self.now = sleep, now
        self.cancelled = cancelled
        self.limiter = RateLimiter(min_interval=max(float(source["min_interval_seconds"]), 1), clock=clock, sleep=sleep)
        self.blocked = False

    def close(self):
        self.client.close()

    def request(self, params):
        if self.blocked:
            raise SourceBlocked("fonte bloqueada nesta execução")
        if params.get("action") not in {"query", "parse"}:
            raise FetchError("somente query/parse de leitura")
        params = {**params, "format": "json", "formatversion": 2, "maxlag": 5}
        attempts = min(int(self.source.get("max_attempts", 3)), 3)
        for attempt in range(attempts):
            if self.cancelled():
                raise KeyboardInterrupt()
            self.limiter.wait()
            try:
                response = self.client.get(API_URL, params=params, follow_redirects=False, headers={
                    "User-Agent": self.source.get("user_agent", USER_AGENT),
                    "Api-User-Agent": f"living-recommender/0.1 ({self.source.get('contact', 'https://github.com/johnosd/living-recommender')})"})
            except httpx.TransportError as error:
                if attempt + 1 == attempts:
                    raise PendingFetch(f"rede temporariamente indisponível: {error}") from error
                self.sleep(2 ** (attempt + 1))
                continue
            if response.status_code == 403:
                self.blocked = True
                raise SourceBlocked("HTTP 403: interromper sem contorno")
            try:
                document = response.json()
            except (ValueError, UnicodeError):
                document = {}
            if not isinstance(document, dict):
                raise FetchError("resposta JSON não é objeto")
            api_error = document.get("error", {})
            if not isinstance(api_error, dict):
                raise FetchError("erro da API com formato inválido")
            if api_error.get("code") in {"blocked", "autoblocked", "permissiondenied"}:
                self.blocked = True
                raise SourceBlocked(str(api_error))
            retryable = response.status_code in {408, 429, 500, 502, 503, 504} or api_error.get("code") in {"maxlag", "ratelimited", "readonly"}
            if retryable:
                delay = 2 ** (attempt + 1)
                header = response.headers.get("Retry-After")
                if header:
                    try:
                        delay = max(delay, float(header))
                    except ValueError:
                        try:
                            delay = max(delay, (parsedate_to_datetime(header) - self.now()).total_seconds())
                        except (TypeError, ValueError):
                            raise FetchError("Retry-After inválido; não antecipar nova chamada") from None
                retry_at = (self.now() + timedelta(seconds=delay)).isoformat()
                if delay > 60 or attempt + 1 == attempts:
                    raise PendingFetch(f"fonte solicita espera: {response.status_code} {api_error}", retry_at)
                self.sleep(delay)
                continue
            if response.status_code != 200 or api_error or not document:
                raise FetchError(f"resposta inválida: HTTP {response.status_code} {api_error}")
            return document, response.content
        raise FetchError("max_attempts inválido")

    def __call__(self, association):
        params = {"action": "query", "pageids": association["page_id"],
                  "prop": "info|revisions|pageprops|langlinks", "inprop": "url",
                  "rvprop": "ids|timestamp", "lllang": "en", "llprop": "url", "redirects": 1}
        document, raw = self.request(params)
        originals, seen = [raw.decode("utf-8")], set()
        combined = document
        for _ in range(20):
            continuation = document.get("continue")
            if not continuation:
                break
            token = encode(continuation)
            if token in seen:
                raise FetchError("continuação cíclica")
            seen.add(token)
            document, raw_next = self.request({**params, **continuation})
            originals.append(raw_next.decode("utf-8"))
            pages = document.get("query", {}).get("pages", [])
            if len(pages) != 1 or pages[0].get("pageid") != combined["query"]["pages"][0].get("pageid"):
                raise FetchError("identidade alterada na continuação")
            combined["query"]["pages"][0].setdefault("langlinks", []).extend(pages[0].get("langlinks", []))
        else:
            raise FetchError("limite de continuação excedido")
        if len(originals) > 1:
            combined.pop("continue", None)
            combined["_http_responses"] = originals
            raw = encode(combined)
        try:
            revision = combined["query"]["pages"][0]["revisions"][0]["revid"]
        except (KeyError, IndexError, TypeError) as error:
            raise FetchError("artigo sem revisão") from error
        _, content = self.request({"action": "parse", "oldid": revision,
            "prop": "text|tocdata|revid|properties|links|externallinks"})
        return {"metadata": raw, "content": content}
