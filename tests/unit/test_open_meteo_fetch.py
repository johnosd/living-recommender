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


@pytest.mark.parametrize('reason,wait,count', [('Hourly limit', 3605, 1), ('Minutely limit', 61, 5),
                                               ('unknown limit', 3605, 1), ('Daily limit', 0, 0)])
def test_quota_waits_are_bounded_and_never_leave_partial_files(tmp_path, reason, wait, count):
    requests, sleeps = [], []

    def respond(request):
        requests.append(request)
        return httpx.Response(429, text=error_response(reason))

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        fetch = make_open_meteo_fetcher(catalog(1)['open_meteo'], client=client, sleep=sleeps.append)
        with pytest.raises(QuotaExhausted, match=reason):
            fetch(ITEM, tmp_path / 'out.json')
    assert sleeps == [wait] * count and len(requests) == count + 1
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('kind', ['timeout', '500', '408', '400', 'html', 'broken_json'])
def test_http_errors_retry_only_transient_failures(tmp_path, kind):
    requests, sleeps = [], []

    def respond(request):
        requests.append(request)
        if kind == 'timeout':
            raise httpx.ReadTimeout('slow', request=request)
        if kind == 'html':
            return httpx.Response(200, text='<html>error</html>', headers={'content-type': 'text/html'})
        if kind == 'broken_json':
            return httpx.Response(200, text='{broken')
        return httpx.Response(int(kind), text=error_response('bad parameter'))

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        fetch = make_open_meteo_fetcher(catalog(1)['open_meteo'], client=client, sleep=sleeps.append)
        with pytest.raises(DownloadError):
            fetch(ITEM, tmp_path / 'out.json')
    transient = kind in ('timeout', '500', '408')
    assert len(requests) == (3 if transient else 1)
    assert sleeps == ([2, 4] if transient else [])
    assert list(tmp_path.iterdir()) == []


def test_rate_limiter_and_no_overwrite(tmp_path, monkeypatch):
    from pipelines.collectors.open_meteo import fetch as module

    now, sleeps = [0.0], []

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    real_limiter = module.RateLimiter
    monkeypatch.setattr(module, 'RateLimiter', lambda interval, **kw: real_limiter(
        interval, clock=lambda: now[0], **kw))
    source = catalog(1)['open_meteo']
    source['limits'] = {'min_interval_seconds': 7}
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, text=open_meteo_response()))) as client:
        fetch = make_open_meteo_fetcher(source, client=client, sleep=sleep)
        fetch(ITEM, tmp_path / 'a.json')
        fetch(ITEM, tmp_path / 'b.json')
        with pytest.raises(FileExistsError):
            fetch(ITEM, tmp_path / 'a.json')
    assert sleeps == [7]
