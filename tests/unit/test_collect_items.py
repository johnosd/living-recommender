import json

import pytest

from pipelines.collectors._shared.dataset_manifest import latest_dataset_states
from pipelines.collectors._shared.datasets import QuotaExhausted, collect_items
from tests.fixtures.open_meteo.responses import MemoryStorage


def invoke(tmp_path, storage, fetcher, *, run_id='one', **options):
    return collect_items(
        {'license_id': 'CC-BY-4.0', 'collection_method': 'api_json'},
        [{'id': str(n), 'collection_method': 'api_json'} for n in range(3)],
        source_id='test', storage=storage, fetcher=fetcher, validator=lambda *_: None,
        run_id=run_id, collected_at_utc='2026-11-11T12:00:00Z',
        work_dir=tmp_path / run_id, **options,
    )


@pytest.mark.parametrize('stop', [QuotaExhausted('daily'), KeyboardInterrupt()])
def test_stop_cleans_current_and_saves_pending(tmp_path, stop):
    storage = MemoryStorage()

    def fetch(item, path):
        path.write_text('content')
        if item['id'] == '1':
            raise stop
        return {'entry_extra': {'model': 'era5'}}

    result = invoke(tmp_path, storage, fetch)
    assert [e['status'] for e in result['datasets']] == ['changed', 'pending', 'pending']
    assert result['quota_exhausted'] == isinstance(stop, QuotaExhausted)
    assert result['interrupted'] == isinstance(stop, KeyboardInterrupt)
    assert len([k for k in storage.list_keys() if k.startswith('raw/')]) == 1
    assert set(latest_dataset_states(storage, 'test')) == {'0'}
    assert json.loads(storage.get(result['manifest_key']))['status'] == 'partial'
    assert not (tmp_path / 'one').exists()


def test_limit_current_noop_and_extras(tmp_path):
    storage = MemoryStorage()

    def fetch(item, path):
        path.write_text('content')
        return {'entry_extra': {'model': 'era5'}}

    first = invoke(tmp_path, storage, fetch, max_items=2)
    assert len(first['datasets']) == 2 and first['remaining'] == 1
    second = invoke(tmp_path, storage, fetch, run_id='two')
    assert [e['status'] for e in second['datasets']] == ['unchanged', 'unchanged', 'changed']
    assert all(e['model'] == 'era5' for e in second['datasets'])
    result = invoke(tmp_path, storage, lambda *_: pytest.fail('fetch'), run_id='one',
                    skip_current=True, state_is_current=lambda item, state: state['model'] == 'era5')
    assert result['up_to_date'] and result['manifest_key'] is None
    assert result['skipped_current'] == 3


def test_interrupt_during_upload_removes_the_current_raw(tmp_path):
    class InterruptedStorage(MemoryStorage):
        def put_file(self, key, path):
            super().put_file(key, path)
            if '/dataset=1/' in key:
                raise KeyboardInterrupt()

    storage = InterruptedStorage()

    def fetch(item, path):
        path.write_text('content')

    result = invoke(tmp_path, storage, fetch)
    assert result['interrupted']
    assert len([k for k in storage.list_keys() if k.startswith('raw/')]) == 1
    assert all(e['key'] is None for e in result['datasets'][1:])


def test_remaining_and_skip_only_current(tmp_path):
    storage = MemoryStorage()
    calls = []

    def fetch(item, path):
        calls.append(item['id'])
        path.write_text('content')

    invoke(tmp_path, storage, fetch, max_items=1)
    calls.clear()
    result = invoke(tmp_path, storage, fetch, run_id='next', skip_current=True,
                    state_is_current=lambda *_: True, max_items=1)
    assert calls == ['1'] and result['remaining'] == 1 and result['skipped_current'] == 1
    assert all(e['status'] != 'pending' for e in result['datasets'])
