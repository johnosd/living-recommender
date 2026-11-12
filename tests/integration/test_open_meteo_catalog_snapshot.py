import json
from copy import deepcopy

import httpx
import pytest

from pipelines.cli import collect_open_meteo as cli
from pipelines.collectors._shared.dataset_manifest import latest_dataset_states
from pipelines.collectors.open_meteo.fetch import make_open_meteo_fetcher
from pipelines.collectors.open_meteo.handler import variables_signature
from tests.fixtures.open_meteo.responses import (
    MemoryStorage,
    catalog,
    municipalities,
    open_meteo_response,
)


@pytest.mark.parametrize('change', ['model', 'window', 'variables'])
def test_catalog_is_frozen_between_checkpoints_and_changes_apply_on_next_session(tmp_path, monkeypatch, change):
    config = catalog(11)
    original = deepcopy(config)
    storage, requests, loads, factories = MemoryStorage(), [], [], []

    def load(*args):
        loads.append(True)
        return config

    def respond(request):
        params = request.url.params
        requests.append(dict(params))
        doc = json.loads(open_meteo_response(start=params['start_date'], end=params['end_date']))
        names = params['daily'].split(',')
        doc['daily'] = {k: v for k, v in doc['daily'].items() if k == 'time' or k in names}
        if len(requests) == 10:
            if change == 'model':
                config['open_meteo']['model'] = 'era5_land'
            elif change == 'window':
                config['open_meteo']['window']['start'] = '2025-01-02'
            else:
                config['open_meteo']['variables'].pop()
        return httpx.Response(200, json=doc)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        def factory(source, **kwargs):
            factories.append(source)
            return make_open_meteo_fetcher(source, client=client, sleep=lambda _: None, **kwargs)

        monkeypatch.setattr(cli, 'load_catalog', load)
        monkeypatch.setattr(cli, 'make_open_meteo_fetcher', factory)
        monkeypatch.setattr(cli, 'load_climate_municipalities', lambda _: municipalities(11))
        args = ['--root', str(tmp_path), '--continuous']
        assert cli.main(args, storage=storage) == 0
        assert len(requests) == 11 and len(loads) == len(factories) == 1
        first_states = latest_dataset_states(storage, 'open_meteo')
        original_keys = {s['key'] for s in first_states.values()}
        for state in first_states.values():
            assert state['model'] == original['open_meteo']['model']
            assert state['reference_period'] == '2025-01-01/2025-01-05'
            assert state['variables_signature'] == variables_signature(original['open_meteo'])
        for request in requests:
            assert request['models'] == 'era5' and request['start_date'] == '2025-01-01'
            assert set(request['daily'].split(',')) == {v['id'] for v in original['open_meteo']['variables']}

        assert cli.main(args, storage=storage) == 0
        assert len(requests) == 22 and len(loads) == len(factories) == 2
        source = config['open_meteo']
        for state in latest_dataset_states(storage, 'open_meteo').values():
            assert state['model'] == source['model']
            assert state['reference_period'] == f"{source['window']['start']}/{source['window']['end']}"
            assert state['variables_signature'] == variables_signature(source)
        for request in requests[11:]:
            assert request['models'] == source['model'] and request['start_date'] == source['window']['start']
            assert set(request['daily'].split(',')) == {v['id'] for v in source['variables']}
        assert original_keys <= storage.list_keys()
