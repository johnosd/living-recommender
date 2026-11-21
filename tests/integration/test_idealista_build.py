"""Integração local: importação, dbt, promoção e preservação da base vigente."""

import hashlib
import json

import pandas as pd
import pytest

from pipelines.cli import build_idealista as module
from pipelines.collectors._shared.catalog import load_catalog
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors.idealista.snapshot import IdealistaError, import_snapshot
from tests.fixtures.idealista.ci_seed import seed

OUTPUTS = ("lake/bronze/idealista_occurrences/data.parquet", "lake/silver/idealista_listings/data.parquet",
           "lake/bronze/idealista_reports/summary.json", "lake/bronze/idealista_reports/coverage.csv",
           "lake/bronze/idealista_reports/duplicates.csv")


def digests(root):
    return {relative: hashlib.sha256((root / relative).read_bytes()).hexdigest() for relative in OUTPUTS}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("idealista")
    seed(root, prepare=False)
    result = module.build_idealista(root, snapshot_month="2025-08")
    return root, result


def test_dbt_build_and_reports_match_the_manual_snapshot(built):
    root, result = built
    assert result["unique_listings"] == 4 and result["records"] == 5
    frame = pd.read_parquet(root / OUTPUTS[1]).set_index("listing_id")
    assert len(frame) == 4 and frame.index.is_unique
    assert frame.loc["101", "asking_rent_eur"] == 1200 and frame.loc["101", "duplicate_count"] == 1
    assert frame.loc["103", "dicofre"] == "110601"
    assert pd.isna(frame.loc["104", "dico"]) and frame.loc["104", "locality_level"] == "regiao"
    assert frame["collected_at_utc"].isna().all()
    assert len(pd.read_parquet(root / OUTPUTS[0])) == 5
    coverage = pd.read_csv(root / OUTPUTS[3], sep=";", dtype=str)
    assert coverage.loc[coverage.territory == "0101", "listings"].item() == "0"
    assert json.loads((root / OUTPUTS[2]).read_text(encoding="utf-8"))["snapshot_month"] == "2025-08"


def test_dbt_failure_preserves_every_previous_output_and_other_sources(built, monkeypatch):
    root, _ = built
    before = digests(root)
    dimension = root / "lake/silver/dim_municipality/data.parquet"
    dim_before = dimension.read_bytes()

    def fail(*args):
        raise IdealistaError("dbt falhou propositalmente")

    monkeypatch.setattr(module, "_run_dbt", fail)
    with pytest.raises(IdealistaError, match="dbt"):
        module.build_idealista(root, snapshot_month="2025-08")
    assert before == digests(root) and dim_before == dimension.read_bytes()
    assert not list((root / ".build/idealista").iterdir())


def test_tampered_raw_cannot_replace_previous_outputs(built):
    root, _ = built
    before = digests(root)
    raw = next((root / "raw").rglob("*.json"))
    original = raw.read_bytes()
    try:
        raw.write_text("[]", encoding="utf-8")
        with pytest.raises(IdealistaError, match="checksum"):
            module.build_idealista(root, snapshot_month="2025-08")
        assert before == digests(root)
    finally:
        raw.write_bytes(original)


def test_cli_errors_and_output_are_console_safe(built, capsys):
    root, _ = built
    assert module.main(["--root", str(root), "--snapshot-month", "2025-09"]) == 1
    capsys.readouterr().err.encode("cp1252")


def test_an_empty_snapshot_is_reported_as_zero_without_phantom_listings(tmp_path):
    root = tmp_path / "lake"
    seed(root, prepare=False)
    source = tmp_path / "empty-source"
    source.mkdir()
    (source / "Porto.json").write_text("[]", encoding="utf-8")
    import_snapshot(load_catalog(), storage=LocalStorage(root), directory=source,
                    snapshot_month="2025-08", run_id="zero", imported_at_utc="2026-11-13T13:00:00Z")
    result = module.build_idealista(root, snapshot_month="2025-08")
    assert result["unique_listings"] == 0 and result["records"] == 0
    assert len(pd.read_parquet(root / OUTPUTS[0])) == len(pd.read_parquet(root / OUTPUTS[1])) == 0
