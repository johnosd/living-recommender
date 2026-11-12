import httpx
import pytest

from pipelines.collectors._shared.datasets import QuotaExhausted
from pipelines.collectors._shared.http import DownloadError
from pipelines.collectors.open_meteo.fetch import make_open_meteo_fetcher
from tests.fixtures.open_meteo.responses import (
    catalog,
    error_response,
    open_meteo_response,
)

ITEM = {'id': '0001', 'latitude': 38.72, 'longitude': -9.14}


@pytest.mark.parametrize('headers,expected', [
    ({'Retry-After': '42'}, 42),
    ({'X-RateLimit-Reset': '1120'}, 120),
    ({'Retry-After': 'bad', 'X-RateLimit-Reset': '1120'}, 120),
    ({'Retry-After': 'Wed, 11 Nov 2026 23:00:00 GMT',
      'Date': 'Wed, 11 Nov 2026 22:00:00 GMT'}, 3600),
    ({'Retry-After': '-1'}, 86405),
    ({'Retry-After': 'NaN', 'X-RateLimit-Reset': 'inf'}, 86405),
])
def test_daily_pause_exposes_provider_delay_without_sleeping(tmp_path, headers, expected):
    quota, sleeps = [], []
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(
        429, text=error_response('Daily API request limit exceeded'), headers=headers))) as client:
        fetch = make_open_meteo_fetcher(catalog(1)['open_meteo'], client=client,
                                       sleep=sleeps.append, clock=lambda: 1000,
                                       on_quota=quota.append, jitter=lambda: 0)
        with pytest.raises(QuotaExhausted):
            fetch(ITEM, tmp_path / 'out.json')
    assert sleeps == [] and quota == [expected]
    assert not (tmp_path / 'out.json').exists()


def test_continuous_transient_retries_are_capped_and_can_recover_after_six_failures(tmp_path):
    calls, sleeps = [], []

    def respond(request):
        calls.append(request)
        if len(calls) <= 8:
            return httpx.Response(503, text='temporarily unavailable')
        return httpx.Response(200, text=open_meteo_response())

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        make_open_meteo_fetcher(catalog(1)['open_meteo'], client=client, sleep=sleeps.append,
                               max_attempts=None, jitter=lambda: 0)(ITEM, tmp_path / 'out.json')
    assert len(calls) == 9 and sleeps == [2, 4, 8, 16, 32, 60, 60, 60]


def test_retry_after_on_service_unavailable_and_jitter_are_respected(tmp_path):
    replies = iter([httpx.Response(503, headers={'Retry-After': '90'}),
                    httpx.Response(200, text=open_meteo_response())])
    sleeps = []
    with httpx.Client(transport=httpx.MockTransport(lambda _: next(replies))) as client:
        make_open_meteo_fetcher(catalog(1)['open_meteo'], client=client, sleep=sleeps.append,
                               jitter=lambda: 0.5)(ITEM, tmp_path / 'out.json')
    assert sleeps == [90.5]


def test_continuous_does_not_retry_invalid_parameters(tmp_path):
    sleeps = []
    with (httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(400, text='bad parameter'))) as client,
          pytest.raises(DownloadError)):
        make_open_meteo_fetcher(catalog(1)['open_meteo'], client=client, sleep=sleeps.append,
                               max_attempts=None)(ITEM, tmp_path / 'out.json')
    assert sleeps == []
