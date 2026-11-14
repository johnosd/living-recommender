from copy import deepcopy

import pytest

from pipelines.collectors._shared.catalog import (
    CatalogError,
    get_climate_source,
    load_catalog,
)
from tests.fixtures.open_meteo.responses import catalog


def test_real_catalog_and_existing_sources():
    loaded = load_catalog()
    assert set(loaded['sources']) == {'caop', 'pordata', 'ine', 'open_meteo', 'ine_parish_crosswalk', 'idealista', 'censos'}
    assert get_climate_source(loaded)['model'] == 'era5'


@pytest.mark.parametrize('change', ['window', 'variables', 'api_url', 'expected_municipalities'])
def test_reject_invalid_source(change):
    data = deepcopy(catalog(308))
    source = data['open_meteo']
    source[change] = {
        'window': {'start': '2025-02-01', 'end': '2025-01-01'},
        'variables': [{'id': 'x', 'unit': 's'}, {'id': 'x', 'unit': 's'}],
        'api_url': 'http://example.com', 'expected_municipalities': 0,
    }[change]
    with pytest.raises(CatalogError):
        get_climate_source(data)


def test_missing_source():
    with pytest.raises(CatalogError):
        get_climate_source({})
