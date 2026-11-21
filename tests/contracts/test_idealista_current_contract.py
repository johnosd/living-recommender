"""Contratos 007, exclusivamente sintéticos; FR-002 a FR-006."""

import json

import pandas as pd
import pytest

from pipelines.collectors.idealista.prepare import prepare_snapshot
from pipelines.collectors.idealista.report import write_report
from pipelines.collectors.idealista.snapshot import IdealistaError
from tests.contracts.test_idealista_import_contract import (
    MONTH,
    NOW,
    dimensions,
    import_run,
    listing,
    write_file,
)


def test_fr003_explicit_parish_wins_over_title_and_preserves_metadata(tmp_path):
    source, root, output = tmp_path / "source", tmp_path / "lake", tmp_path / "out"
    dimensions(root)
    row = listing(Titulo="Apartamento, desconhecida", **{
        "Região": "Norte", "Sub-região": "Porto", "Município": "Porto", "Freguesia": "Bonfim"})
    write_file(source, "Porto-Paginas1.json", [row])
    import_run(source, root)
    prepare_snapshot(root, output, snapshot_month=MONTH, processed_at_utc=NOW, parish_synonyms=[])
    actual = pd.read_parquet(output / "listings.parquet").iloc[0]
    assert pd.notna(actual.dicofre) and actual.dicofre == "131203"
    assert actual.source_parish == "Bonfim" and actual.source_subregion == "Porto"


def test_fr002_district_named_porto_is_regional_even_with_matching_title(tmp_path):
    source, root, output = tmp_path / "source", tmp_path / "lake", tmp_path / "out"
    dimensions(root)
    row = listing(**{"Região": "Norte", "Sub-região": "Porto", "Município": None, "Freguesia": "Bonfim"})
    write_file(source, "Porto-Paginas1.json", [row])
    import_run(source, root)
    summary = prepare_snapshot(root, output, snapshot_month=MONTH, processed_at_utc=NOW, parish_synonyms=[])
    actual = pd.read_parquet(output / "listings.parquet").iloc[0]
    assert pd.isna(actual.dico) and pd.isna(actual.dicofre)
    assert actual.locality_level == "regiao" and summary["municipalities_with_listings"] == 0


def test_fr002_partial_metadata_is_rejected_before_raw_commit(tmp_path):
    source, root = tmp_path / "source", tmp_path / "lake"
    write_file(source, "Porto.json", [listing(Município="Porto")])
    with pytest.raises(IdealistaError, match="territoria"):
        import_run(source, root)
    assert not (root / "raw").exists()


def test_fr005_report_suppresses_small_groups_and_excludes_conflicting_prices(tmp_path):
    rows = [{"dico": "1312", "typology": "T1", "asking_rent_eur": 100 + 100 * i,
             "conflict_fields": "", "listing_id": str(i)} for i in range(10)]
    rows += [{"dico": "1106", "typology": "T2", "asking_rent_eur": 999999,
              "conflict_fields": "asking_rent_eur", "listing_id": "private"}]
    rows += [{"dico": "1106", "typology": "T2", "asking_rent_eur": 900,
              "conflict_fields": "", "listing_id": "private2"}]
    municipalities = pd.DataFrame({"dico": ["1312", "1106"], "official_name": ["Porto", "Lisboa"]})
    summary = {"snapshot_month": MONTH, "source_run_id": "test", "snapshot_sha256": "a" * 64,
               "license_id": "restricted", "attribution": "Idealista", "unique_listings": 12}
    write_report(pd.DataFrame(rows), municipalities, summary, tmp_path)
    stats = pd.read_csv(tmp_path / "municipality_stats.csv", sep=";", dtype={"dico": str}).set_index("dico")
    assert stats.loc["1312", "median_eur"] == 550
    assert stats.loc["1312", "p25_eur"] == 325 and stats.loc["1312", "p75_eur"] == 775
    assert stats.loc["1106", "n_eligible"] == 1 and pd.isna(stats.loc["1106", "median_eur"])
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "amostra insuficiente" in report and "2025-08" in report
    assert "private" not in report and "999999" not in report
    assert json.loads((tmp_path / "statistics.json").read_text())["snapshot_month"] == MONTH
