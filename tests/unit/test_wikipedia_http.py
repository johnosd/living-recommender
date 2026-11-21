from datetime import UTC, datetime

import httpx
import pytest

from pipelines.collectors.wikipedia.catalog import API_URL, wikipedia_source
from pipelines.collectors.wikipedia.fetch import (
    FetchError,
    PendingFetch,
    SourceBlocked,
    WikipediaFetcher,
)
from tests.fixtures.wikipedia.responses import associations, catalog, documents


class Clock:
    def __init__(self):
        self.value, self.sleeps = 0, []

    def sleep(self, delay):
        self.value += delay
        self.sleeps.append(delay)

    def __call__(self):
        return self.value


def adapter(responses):
    clock, requests = Clock(), []

    def respond(request):
        assert str(request.url).startswith(API_URL + "?")
        assert "living-recommender" in request.headers["user-agent"]
        assert request.url.params["maxlag"] == "5"
        requests.append(request)
        return responses.pop(0)

    client = httpx.Client(transport=httpx.MockTransport(respond))
    fetch = WikipediaFetcher(wikipedia_source(catalog()), client=client, sleep=clock.sleep,
                            clock=clock, now=lambda: datetime(2026, 11, 20, tzinfo=UTC))
    return fetch, clock, requests


@pytest.mark.parametrize("status,body", [(429, {}), (503, {}), (200, {"error": {"code": "maxlag"}})])
def test_wikipedia_retry_and_rate_limit(status, body):
    fetch, clock, calls = adapter([httpx.Response(status, json=body, headers={"Retry-After": "4"}),
                                  httpx.Response(200, json={"query": {}})])
    fetch.request({"action": "query"})
    assert len(calls) == 2 and clock.sleeps == [4]


@pytest.mark.parametrize("header", ["120", "Fri, 20 Nov 2026 00:02:00 GMT"])
def test_wikipedia_long_retry_after_becomes_pending(header):
    fetch, clock, calls = adapter([httpx.Response(429, json={}, headers={"Retry-After": header})])
    with pytest.raises(PendingFetch) as error:
        fetch.request({"action": "query"})
    assert error.value.retry_at == "2026-11-20T00:02:00+00:00"
    assert len(calls) == 1 and not clock.sleeps


def test_wikipedia_block_stops_all_further_requests():
    fetch, _, calls = adapter([httpx.Response(403)])
    for _ in range(2):
        with pytest.raises(SourceBlocked):
            fetch.request({"action": "query"})
    assert len(calls) == 1


@pytest.mark.parametrize("response", [httpx.Response(200, json={"error": {"code": "badrevids"}}),
                                     httpx.Response(200, json=[]), httpx.Response(200, json={"error": "bad"}),
                                     httpx.Response(302, headers={"Location": "https://evil.test"}),
                                     httpx.Response(200, text="<html>error</html>")])
def test_wikipedia_body_errors_and_redirect_rejected(response):
    fetch, _, calls = adapter([response])
    with pytest.raises(FetchError):
        fetch.request({"action": "query"})
    assert len(calls) == 1


def test_wikipedia_revision_pinned_continuation_keeps_original_responses():
    meta, parsed = documents()
    meta["continue"] = {"continue": "||", "llcontinue": "next"}
    continued = {"query": {"pages": [{"pageid": 101, "langlinks": []}]}}
    fetch, clock, calls = adapter([httpx.Response(200, json=meta), httpx.Response(200, json=continued),
                                  httpx.Response(200, json=parsed)])
    result = fetch(associations()[0])
    import json
    assert len(json.loads(result["metadata"])["_http_responses"]) == 2
    assert calls[-1].url.params["oldid"] == "1001"
    assert "tocdata" in calls[-1].url.params["prop"]
    assert clock.sleeps == [1, 1]


def test_wikipedia_retry_exhaustion_and_write_action():
    fetch, _, calls = adapter([httpx.Response(503, json={}) for _ in range(3)])
    with pytest.raises(PendingFetch):
        fetch.request({"action": "query"})
    assert len(calls) == 3
    with pytest.raises(FetchError):
        fetch.request({"action": "edit"})
