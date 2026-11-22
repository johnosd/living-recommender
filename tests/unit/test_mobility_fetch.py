"""Cliente HTTP da Routes API: requisição, retry, parada em cota/autorização e redação (spec 009, FR-010/012)."""
import json

import httpx
import pytest

from pipelines.collectors._shared.datasets import QuotaExhausted
from pipelines.collectors._shared.http import DownloadError
from pipelines.collectors.mobility.catalog import mobility_source
from pipelines.collectors.mobility.fetch import (
    AuthorizationStop,
    make_routes_fetcher,
    request_body,
)
from pipelines.collectors.mobility.pairs import build_items
from pipelines.collectors.mobility.poles import resolve_poles
from tests.fixtures.mobility.responses import (
    KEY_SENTINEL,
    api_error,
    catalog,
    municipalities,
    raw_poles,
    routes_ok,
)

SOURCE = mobility_source(catalog())


def item(item_id="0102--aeroporto_x--driving"):
    towns = municipalities()
    return next(i for i in build_items(SOURCE, towns, resolve_poles(raw_poles(), towns)) if i["id"] == item_id)


def reply(status, body, headers=None):
    return httpx.Response(status, content=body.encode(), headers={"content-type": "application/json", **(headers or {})})


def fetcher(handler, sleeps=None, **kwargs):
    sleeps = sleeps if sleeps is not None else []
    return make_routes_fetcher(SOURCE, api_key=KEY_SENTINEL, sleep=sleeps.append,
                               client=httpx.Client(transport=httpx.MockTransport(handler)), jitter=lambda: 0.0,
                               **kwargs)


def test_a_success_writes_the_exact_bytes_and_sends_the_documented_request(tmp_path):
    seen = []

    def handler(request):
        seen.append(request)
        return reply(200, routes_ok())

    destination = tmp_path / "out" / "r.json"
    assert fetcher(handler)(item(), destination) == {}
    assert destination.read_bytes() == routes_ok().encode()
    body = json.loads(seen[0].content)
    assert body["origins"][0]["waypoint"]["location"]["latLng"] == {"latitude": 39.0, "longitude": -9.0}
    assert body["destinations"][0]["waypoint"]["location"]["latLng"] == {"latitude": 38.78, "longitude": -9.13}
    assert body["travelMode"] == "DRIVE" and body["routingPreference"] == "TRAFFIC_UNAWARE"
    assert str(seen[0].url) == SOURCE["api_url"] and seen[0].method == "POST"
    assert not list(destination.parent.glob(".download-*"))  # no temporary file is left behind


def test_the_request_body_only_carries_departure_for_transit():
    assert "departureTime" not in request_body(item())
    assert request_body(item("0102--aeroporto_x--transit"))["departureTime"] == SOURCE["modes"]["transit"]["departure_time"]


def test_an_existing_destination_is_never_overwritten(tmp_path):
    destination = tmp_path / "r.json"
    destination.write_text("x")
    with pytest.raises(FileExistsError):
        fetcher(lambda request: reply(200, routes_ok()))(item(), destination)


@pytest.mark.parametrize("status", [401, 403])
def test_authorization_errors_stop_the_collection_without_retrying(tmp_path, status):
    calls = []

    def handler(request):
        calls.append(1)
        return reply(status, api_error("PERMISSION_DENIED", f"key {KEY_SENTINEL} denied", status))

    with pytest.raises(AuthorizationStop) as error:
        fetcher(handler)(item(), tmp_path / "r.json")
    assert len(calls) == 1 and KEY_SENTINEL not in str(error.value) and "[REDACTED]" in str(error.value)


def test_a_429_stops_with_quota_exhausted_and_reports_the_server_delay(tmp_path):
    delays = []
    with pytest.raises(QuotaExhausted, match="cota"):
        fetcher(lambda request: reply(429, api_error("RESOURCE_EXHAUSTED", "quota", 429), {"retry-after": "30"}),
                on_quota=delays.append)(item(), tmp_path / "r.json")
    assert delays == [30.0]  # the provider asked for 30 s


def test_transient_errors_are_retried_with_backoff_and_then_succeed(tmp_path):
    answers = [reply(503, "{}"), reply(500, "{}"), reply(200, routes_ok())]
    sleeps = []
    fetch = fetcher(lambda request: answers.pop(0), sleeps)
    fetch(item(), tmp_path / "r.json")
    waits = [seconds for seconds in sleeps if seconds >= 1]  # the rate limiter also sleeps, in fractions of a second
    assert not answers and waits == [2, 4]  # 2 ** attempt, jitter pinned at zero


def test_a_server_retry_after_wins_over_the_default_backoff(tmp_path):
    answers = [reply(503, "{}", {"retry-after": "20"}), reply(200, routes_ok())]
    sleeps = []
    fetcher(lambda request: answers.pop(0), sleeps)(item(), tmp_path / "r.json")
    assert [seconds for seconds in sleeps if seconds >= 1] == [20]


def test_persistent_failure_gives_up_after_max_attempts_with_a_redacted_message(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        raise httpx.ConnectError(f"cannot reach {request.url} with {request.headers['x-goog-api-key']}")

    with pytest.raises(DownloadError, match="3 tentativas") as error:
        fetcher(handler)(item(), tmp_path / "r.json")
    assert len(calls) == 3 and KEY_SENTINEL not in str(error.value)
    assert not (tmp_path / "r.json").exists()


@pytest.mark.parametrize("response", [
    reply(400, api_error("INVALID_ARGUMENT", "bad", 400)),
    httpx.Response(200, content=b"<html>proxy</html>", headers={"content-type": "text/html"}),
    httpx.Response(200, content=b"not json", headers={"content-type": "application/json"}),
    httpx.Response(200, content=b"[1, 2", headers={"content-type": "application/json"}),
])
def test_permanent_errors_and_non_json_bodies_are_not_retried_and_not_stored(tmp_path, response):
    calls = []

    def handler(request):
        calls.append(1)
        return response

    with pytest.raises(DownloadError):
        fetcher(handler)(item(), tmp_path / "r.json")
    assert len(calls) == 1 and not (tmp_path / "r.json").exists()
