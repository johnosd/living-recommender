import json

from pipelines.collectors.open_meteo.fingerprint import fingerprint_open_meteo_response
from tests.fixtures.open_meteo.responses import open_meteo_response


def test_fingerprint_ignores_generation_and_key_order_but_tracks_data_and_elevation(tmp_path):
    path = tmp_path / 'response.json'
    path.write_text(open_meteo_response(), encoding='utf-8')
    original = fingerprint_open_meteo_response(path)
    doc = json.loads(open_meteo_response(generation_ms=999))
    path.write_text(json.dumps(dict(reversed(list(doc.items())))), encoding='utf-8')
    assert fingerprint_open_meteo_response(path) == original
    doc['elevation'] += 1
    path.write_text(json.dumps(doc), encoding='utf-8')
    assert fingerprint_open_meteo_response(path) != original
    doc['elevation'] -= 1
    doc['daily']['precipitation_sum'][0] += 1
    path.write_text(json.dumps(doc), encoding='utf-8')
    assert fingerprint_open_meteo_response(path) != original
