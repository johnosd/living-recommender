import json

import pandas as pd

from pipelines.cli.collect_open_meteo import main
from tests.fixtures.open_meteo.responses import municipalities, open_meteo_response


def write_silver(root, count=308):
    towns = municipalities(count)
    path = root / 'lake/silver/dim_municipality/data.parquet'
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(towns).rename(columns={'name': 'official_name', 'latitude': 'representative_lat',
                                       'longitude': 'representative_lon'}).to_parquet(path, index=False)


def offline(item, path):
    path.write_text(open_meteo_response(start=item['window']['start'], end=item['window']['end']),
                    encoding='utf-8')


def test_cli_308_recollection_and_noop(tmp_path):
    write_silver(tmp_path)
    args = ['--local', '--root', str(tmp_path)]
    assert main(args, fetcher=offline) == 0
    assert len(list((tmp_path / 'raw').rglob('*.json'))) == 308
    assert main(args + ['--recollect'], fetcher=offline) == 0
    manifests = [json.loads(p.read_text()) for p in (tmp_path / 'manifests/open_meteo').glob('*.json')]
    assert {m['status'] for m in manifests} == {'changed', 'unchanged'}
    assert main(args, fetcher=lambda *_: (_ for _ in ()).throw(AssertionError('fetch'))) == 0
    assert len(list((tmp_path / 'raw').rglob('*.json'))) == 308


def test_cli_failure_is_isolated_and_missing_dimension_refused(tmp_path):
    write_silver(tmp_path)
    calls = []

    def fetch(item, path):
        calls.append(item['id'])
        if item['id'] == '0002':
            raise ValueError('bad town')
        offline(item, path)

    args = ['--root', str(tmp_path)]
    assert main(args, fetcher=fetch) == 1
    assert len(calls) == 308 and len(list((tmp_path / 'raw').rglob('*.json'))) == 307
    write_silver(tmp_path, 307)
    calls.clear()
    assert main(args, fetcher=fetch) == 1 and calls == []
