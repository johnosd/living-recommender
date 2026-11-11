import datetime
import json

import pytest

from pipelines.collectors.open_meteo.transform import read_climate_response
from tests.fixtures.open_meteo.responses import VARIABLES, open_meteo_response


@pytest.mark.parametrize('start,end', [('2024-02-28', '2024-03-01'), ('2024-12-31', '2025-01-02')])
def test_dates_nulls_zero_and_units(tmp_path, start, end):
    doc = json.loads(open_meteo_response(start=start, end=end))
    for values in doc['daily'].values():
        if values is not doc['daily']['time']:
            values[1] = None
    doc['daily']['precipitation_sum'][0] = 0
    path = tmp_path / 'response.json'
    path.write_text(json.dumps(doc), encoding='utf-8')
    frame = read_climate_response(path)
    assert len(frame) == 39 and frame['value'].isna().sum() == 13
    assert sorted(set(frame['date'])) == [datetime.date.fromisoformat(s) for s in doc['daily']['time']]
    assert frame[frame.variable == 'precipitation_sum']['value'].iloc[0] == 0
    assert dict(zip(frame.variable, frame.unit, strict=True)) == VARIABLES
