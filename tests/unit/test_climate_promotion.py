import os
from pathlib import Path

import pytest

from pipelines.cli.build_climate import PROMOTED, _promote_climate

PATHS = (*PROMOTED, 'lake/bronze/climate_coverage.csv', 'lake/bronze/climate_points.csv')


@pytest.mark.parametrize('blocked', PATHS)
def test_any_locked_destination_rolls_back_all_tables_and_csv(tmp_path, monkeypatch, blocked):
    root, candidate = tmp_path / 'root', tmp_path / 'candidate'
    for relative in PATHS:
        for parent, content in [(root, b'old'), (candidate, b'new')]:
            path = parent / relative
            if not relative.endswith('.csv'):
                path /= 'data.parquet'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    replace = os.replace
    failed = []

    def fail(source, destination):
        if Path(source) == candidate / blocked and not failed:
            failed.append(True)
            raise PermissionError('arquivo aberto no Excel')
        return replace(source, destination)

    monkeypatch.setattr(os, 'replace', fail)
    with pytest.raises(PermissionError, match='Excel'):
        _promote_climate(root, candidate)
    for relative in PATHS:
        path = root / relative
        if not relative.endswith('.csv'):
            path /= 'data.parquet'
        assert path.read_bytes() == b'old'
    assert not list(root.rglob('.previous-*'))
