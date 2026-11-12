import json

import pytest

from pipelines.collectors.open_meteo.validate import validate_open_meteo_response
from tests.fixtures.open_meteo.responses import catalog, open_meteo_response


@pytest.mark.parametrize('problem', [
    'empty', 'html', 'list', 'error', 'daily', 'units', 'days_short', 'days_extra',
    'variable', 'length', 'unit', 'text', 'bool', 'null', 'coordinates', 'timezone',
])
def test_invalid_response(tmp_path, problem):
    doc = json.loads(open_meteo_response())
    var = 'temperature_2m_mean'
    if problem == 'error':
        doc.update(error=True, reason='invalid parameter')
    elif problem == 'daily':
        doc['daily'] = []
    elif problem == 'units':
        doc['daily_units'] = []
    elif problem == 'days_short':
        doc['daily']['time'].pop()
    elif problem == 'days_extra':
        doc['daily']['time'].append('2025-01-06')
    elif problem == 'variable':
        doc['daily'].pop(var)
    elif problem == 'length':
        doc['daily'][var].pop()
    elif problem == 'unit':
        doc['daily_units'][var] = 'F'
    elif problem in ('text', 'bool'):
        doc['daily'][var][0] = '12' if problem == 'text' else True
    elif problem == 'null':
        doc['daily'][var] = [None] * 5
    elif problem == 'coordinates':
        doc.pop('latitude')
    elif problem == 'timezone':
        doc.pop('timezone')
    body = {'empty': '', 'html': '<html>oops</html>', 'list': '[]'}.get(problem, json.dumps(doc))
    path = tmp_path / 'response.json'
    path.write_text(body, encoding='utf-8')
    with pytest.raises(ValueError):
        validate_open_meteo_response(catalog(1)['open_meteo'], path)


def test_sparse_nulls_and_zero_are_valid(tmp_path):
    path = tmp_path / 'response.json'
    doc = json.loads(open_meteo_response(nulls={'precipitation_sum': {1}}))
    doc['daily']['precipitation_sum'][0] = 0
    path.write_text(json.dumps(doc), encoding='utf-8')
    validate_open_meteo_response(catalog(1)['open_meteo'], path)
