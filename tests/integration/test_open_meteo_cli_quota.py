import json

import httpx
import pytest

from pipelines.cli import collect_open_meteo as cli
from pipelines.collectors._shared.datasets import QuotaExhausted
from pipelines.collectors.open_meteo.fetch import make_open_meteo_fetcher
from tests.fixtures.open_meteo.responses import catalog, error_response
from tests.integration.test_open_meteo_cli_local import offline, write_silver


def test_quota_resume_limit_and_noop(tmp_path):
    write_silver(tmp_path)
    args, calls = ['--root', str(tmp_path)], []

    def fetch(item, path):
        calls.append(item['id'])
        if len(calls) > 2:
            raise QuotaExhausted('daily')
        offline(item, path)

    assert cli.main(args, fetcher=fetch) == 2
    assert calls == ['0001', '0002', '0003']
    calls.clear()

    def ok(item, path):
        calls.append(item['id'])
        offline(item, path)

    assert cli.main(args + ['--max-municipalities', '2'], fetcher=ok) == 0
    assert calls == ['0003', '0004']
    calls.clear()
    assert cli.main(args, fetcher=ok) == 0
    assert len(calls) == 304 and calls[0] == '0005'
    assert cli.main(args, fetcher=lambda *_: (_ for _ in ()).throw(AssertionError('fetch'))) == 0


def test_interrupt_persists_manifest_and_failure_wins(tmp_path):
    write_silver(tmp_path)

    def interrupt(item, path):
        if item['id'] == '0001':
            raise KeyboardInterrupt()
        offline(item, path)

    args = ['--root', str(tmp_path)]
    assert cli.main(args, fetcher=interrupt) == 2
    doc = json.loads(next((tmp_path / 'manifests/open_meteo').glob('*.json')).read_text())
    assert len(doc['datasets']) == 308 and all(e['status'] == 'pending' for e in doc['datasets'])

    def mixed(item, path):
        if item['id'] == '0001':
            raise ValueError('bad data')
        raise QuotaExhausted('daily')

    assert cli.main(args, fetcher=mixed) == 1


def test_no_wait_maps_minute_limit_to_pending(tmp_path, monkeypatch):
    write_silver(tmp_path)
    sleeps = []
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(
        429, text=error_response('Minutely limit')))) as client:
        monkeypatch.setattr(cli, 'make_open_meteo_fetcher', lambda source, **kw: make_open_meteo_fetcher(
            catalog(308)['open_meteo'], client=client, sleep=sleeps.append, **kw))
        assert cli.main(['--root', str(tmp_path), '--no-wait']) == 2
    assert sleeps == []


def test_continuous_checkpoints_before_quota_wait_and_resumes_only_pending(tmp_path, monkeypatch):
    write_silver(tmp_path)
    calls, sleeps, options = [], [], []

    def factory(source, **kwargs):
        options.append(kwargs)

        def fetch(item, path):
            calls.append(item['id'])
            if len(calls) == 3:
                kwargs['on_quota'](42)
                raise QuotaExhausted('daily')
            offline(item, path)
        return fetch

    def sleep(seconds):
        manifests = list((tmp_path / 'manifests/open_meteo').glob('*.json'))
        doc = json.loads(manifests[0].read_text())
        assert [e['status'] for e in doc['datasets'][:3]] == ['changed', 'changed', 'pending']
        sleeps.append(seconds)

    monkeypatch.setattr(cli, 'make_open_meteo_fetcher', factory)
    assert cli.main(['--root', str(tmp_path), '--continuous'], sleep=sleep) == 0
    assert calls[:4] == ['0001', '0002', '0003', '0003']
    assert len(calls) == 309 and sleeps == [42]
    assert len(options) == 1  # o limitador sobrevive às fronteiras dos checkpoints
    assert all(not o['wait_on_limits'] and o['max_attempts'] is None for o in options)
    assert len(list((tmp_path / 'manifests/open_meteo').glob('*.json'))) > 30


def test_continuous_stops_on_keyboard_interrupt_without_restarting(tmp_path):
    write_silver(tmp_path)
    calls = []

    def fetch(item, path):
        calls.append(item['id'])
        raise KeyboardInterrupt()

    assert cli.main(['--root', str(tmp_path), '--continuous'], fetcher=fetch) == 2
    assert calls == ['0001']


@pytest.mark.parametrize('extra', [['--no-wait'], ['--recollect'], ['--max-municipalities', '5']])
def test_continuous_rejects_conflicting_modes(extra):
    with pytest.raises(SystemExit) as exc:
        cli.main(['--continuous', *extra])
    assert exc.value.code == 2


def test_continuous_interrupt_during_wait_preserves_checkpoint(tmp_path, monkeypatch):
    write_silver(tmp_path)

    def factory(source, **kwargs):
        def fetch(item, path):
            kwargs['on_quota'](120)
            raise QuotaExhausted('daily')
        return fetch

    def interrupt(seconds):
        assert seconds == 60
        raise KeyboardInterrupt()

    monkeypatch.setattr(cli, 'make_open_meteo_fetcher', factory)
    assert cli.main(['--root', str(tmp_path), '--continuous'], sleep=interrupt) == 2
    manifests = list((tmp_path / 'manifests/open_meteo').glob('*.json'))
    assert len(manifests) == 1
    assert all(e['status'] == 'pending' for e in json.loads(manifests[0].read_text())['datasets'])
