import pandas as pd

from pipelines.cli import build_climate as builder
from tests.fixtures.climate.ci_seed import seed


def test_coverage_names_gaps_points_and_csv(tmp_path):
    data = seed(tmp_path, prepare=False, collected=303, gaps=3, diverged=True)
    result = builder.build_climate(tmp_path, catalog=data['catalog'])
    report = result['coverage'].set_index('variable')
    row = report.loc['precipitation_sum']
    assert (row.municipalities_complete, row.municipalities_with_gaps, row.municipalities_not_collected) == (300, 3, 5)
    assert row.missing_days_total == 3
    assert list(row.not_collected_dico) == [f'{n:04d}' for n in range(304, 309)]
    assert [g['dico'] for g in row.gaps] == ['0001', '0002', '0003']
    points = result['points'].set_index('dico')
    assert points.loc['0001'].diverged and points.loc['0001'].elevation_m == 0
    assert not points.loc['0308'].collected and pd.isna(points.loc['0308'].returned_lat)
    for filename in ('climate_coverage.csv', 'climate_points.csv'):
        path = tmp_path / 'lake/bronze' / filename
        assert path.read_bytes().startswith(b'\xef\xbb\xbf')
        assert ';' in path.read_text(encoding='utf-8-sig')
    text = (tmp_path / 'lake/bronze/climate_coverage.csv').read_text(encoding='utf-8-sig')
    assert '0308 Município 0308' in text and '0001 Município 0001' in text
    text = builder.format_coverage(result['coverage'], result['points'])
    assert '2025-01-01' in text and 'era5' in text and 'elevação 0 m: 1' in text


def test_variable_without_rows_has_zero_coverage(tmp_path):
    seed(tmp_path, collected=2)
    path = tmp_path / 'prepared/climate_daily.parquet'
    frame = pd.read_parquet(path)
    frame[frame.variable != 'sunshine_duration'].to_parquet(path, index=False)
    builder._run_dbt(tmp_path.resolve(), (tmp_path / 'lake/silver').resolve())
    coverage = pd.read_parquet(tmp_path / 'lake/bronze/rpt_climate_coverage/data.parquet').set_index('variable')
    assert coverage.loc['sunshine_duration'].municipalities_collected == 0
    assert coverage.loc['sunshine_duration'].municipalities_not_collected == 308
