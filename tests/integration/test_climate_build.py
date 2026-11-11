import json
from datetime import date

import pandas as pd
import pytest

from pipelines.cli import build_climate as builder
from pipelines.collectors._shared.storage import LocalStorage
from tests.fixtures.climate.ci_seed import seed

STAGING = 'lake/bronze/stg_climate_daily/data.parquet'


def test_build_streaming_partial_and_other_lakes_preserved(tmp_path):
    data = seed(tmp_path, prepare=False)
    other = tmp_path / 'lake/bronze/stg_observation/data.parquet'
    other.parent.mkdir(parents=True)
    other.write_bytes(b'previous observations')
    silver = tmp_path / 'lake/silver/dim_municipality/data.parquet'
    before = silver.read_bytes()
    result = builder.build_climate(tmp_path, catalog=data['catalog'])
    assert result['observations'] == 308 * 13 * 31
    frame = pd.read_parquet(tmp_path / STAGING)
    assert all(isinstance(value, date) for value in frame.date)
    assert not frame.duplicated(['dico', 'variable', 'date']).any()
    assert set(frame.dico) == set(pd.read_parquet(silver).dico)
    assert silver.read_bytes() == before and other.read_bytes() == b'previous observations'
    data['catalog']['open_meteo']['window']['end'] = '2025-02-01'
    before = (tmp_path / STAGING).read_bytes()
    with pytest.raises(builder.ClimateBuildError, match='collect_open_meteo'):
        builder.build_climate(tmp_path, catalog=data['catalog'])
    assert (tmp_path / STAGING).read_bytes() == before


def test_partial_collection_is_valid(tmp_path):
    data = seed(tmp_path, prepare=False, collected=3)
    result = builder.build_climate(tmp_path, catalog=data['catalog'])
    assert result['municipalities'] == 3 and len(result['not_collected']) == 305
    assert len(pd.read_parquet(tmp_path / STAGING)) == 3 * 13 * 31


def test_checksum_failure_keeps_previous_staging(tmp_path):
    data = seed(tmp_path, prepare=False, collected=3)
    builder.build_climate(tmp_path, catalog=data['catalog'])
    before = (tmp_path / STAGING).read_bytes()
    storage = LocalStorage(tmp_path)
    doc = json.loads(storage.get('manifests/open_meteo/ci-climate.json'))
    storage.local_path(doc['datasets'][0]['key']).write_text('alterado')
    with pytest.raises(builder.ClimateBuildError, match='checksum ou tamanho alterado'):
        builder.build_climate(tmp_path, catalog=data['catalog'])
    assert (tmp_path / STAGING).read_bytes() == before


def test_real_dbt_range_failure_keeps_previous_staging(tmp_path):
    data = seed(tmp_path, prepare=False, collected=2)
    builder.build_climate(tmp_path, catalog=data['catalog'])
    before = (tmp_path / STAGING).read_bytes()
    # A nova execução contém uma resposta íntegra mas fisicamente inválida: quem reprova é o dbt.
    from pipelines.collectors.open_meteo.handler import collect_open_meteo
    from tests.fixtures.climate.ci_seed import response

    def fetch(item, path):
        doc = json.loads(response(item))
        doc['daily']['relative_humidity_2m_mean'][0] = 120
        path.write_text(json.dumps(doc), encoding='utf-8')

    collect_open_meteo(data['catalog'], municipalities=data['towns'], storage=LocalStorage(tmp_path),
                       fetcher=fetch, run_id='invalid', collected_at_utc='2026-11-11T15:00:00Z',
                       work_dir=tmp_path / '.work/invalid', max_municipalities=1, recollect=True)
    with pytest.raises(builder.ClimateBuildError, match='dbt build falhou'):
        builder.build_climate(tmp_path, catalog=data['catalog'])
    assert (tmp_path / STAGING).read_bytes() == before
