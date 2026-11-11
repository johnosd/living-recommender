import json
from copy import deepcopy

import pytest

from pipelines.collectors._shared.dataset_manifest import latest_dataset_states
from pipelines.collectors.open_meteo.handler import collect_open_meteo
from tests.fixtures.open_meteo.responses import (
    MemoryStorage,
    catalog,
    municipalities,
    open_meteo_response,
)


def test_changed_model_with_identical_json_must_become_a_new_state(tmp_path):
    storage, config, towns, calls = MemoryStorage(), catalog(1), municipalities(1), []

    def fetch(item, path):
        calls.append(item['model'])
        path.write_text(open_meteo_response(), encoding='utf-8')

    def run(config, run_id):
        return collect_open_meteo(config, municipalities=towns, storage=storage, fetcher=fetch,
                                  run_id=run_id, collected_at_utc='2026-11-11T12:00:00Z',
                                  work_dir=tmp_path / run_id)

    run(config, 'one')
    config = deepcopy(config)
    config['open_meteo']['model'] = 'another_model'
    result = run(config, 'two')
    assert result['datasets'][0]['status'] == 'changed'
    assert latest_dataset_states(storage, 'open_meteo')['0001']['model'] == 'another_model'
    assert run(config, 'three')['up_to_date'] and calls == ['era5', 'another_model']


@pytest.mark.parametrize('change', ['add', 'unit', 'order'])
def test_variables_and_units_are_part_of_current_state(tmp_path, change):
    storage, config, calls = MemoryStorage(), catalog(1), []

    def fetch(item, path):
        calls.append(item['id'])
        doc = json.loads(open_meteo_response())
        for variable in item['variables']:
            doc['daily_units'][variable['id']] = variable['unit']
            doc['daily'].setdefault(variable['id'], [1] * len(doc['daily']['time']))
        path.write_text(json.dumps(doc), encoding='utf-8')

    def run(run_id):
        return collect_open_meteo(config, municipalities=municipalities(1), storage=storage, fetcher=fetch,
                                  run_id=run_id, collected_at_utc='2026-11-11T12:00:00Z',
                                  work_dir=tmp_path / run_id)

    run('one')
    variables = config['open_meteo']['variables']
    if change == 'add':
        variables.append({'id': 'soil_temperature', 'unit': '°C'})
    elif change == 'unit':
        variables[0]['unit'] = 'K'
    else:
        variables.reverse()
    result = run('two')
    if change == 'order':
        assert result['up_to_date'] and len(calls) == 1
    else:
        assert result['datasets'][0]['status'] == 'changed' and len(calls) == 2
        assert run('three')['up_to_date']
