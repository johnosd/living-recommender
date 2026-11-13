"""Casos difíceis da importação manual, com dados inteiramente sintéticos."""

import json

import pytest

from pipelines.collectors._shared.catalog import CatalogError, load_catalog
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors.idealista.normalize import normalize_listing
from pipelines.collectors.idealista.prepare import prepare_snapshot
from pipelines.collectors.idealista.snapshot import (
    IdealistaError,
    import_snapshot,
    latest_snapshot,
)


@pytest.mark.parametrize(("price", "expected"), [
    ("1.200€/mês", 1200), ("1.200,50 €/mês", 1200.5), ("950€ / mês", 950),
    (1200, 1200), (None, None), ("Consultar preço", None), ("-100€", None),
    ("1.20€/mês", None), ("1,200.50€", None),
])
def test_price_locale_and_no_silent_multiplication(price, expected):
    result = normalize_listing({"Preco": price, "tipologia": "T2", "areaBrutaM2": 80})
    assert result["asking_rent_eur"] == expected
    if expected is None:
        assert "price" in result["quality_flags"]


def test_missing_area_typology_and_invalid_values_are_flagged():
    result = normalize_listing({"Preco": "120€", "tipologia": "T5", "areaBrutaM2": None})
    assert result["asking_rent_eur"] == 120  # sem multiplicar preço baixo
    assert result["area_m2"] is None and "area" in result["quality_flags"]
    assert result["typology"] == "T4+" and result["bedrooms"] == 5
    result = normalize_listing({"Preco": None, "tipologia": "quarto", "areaBrutaM2": -10})
    assert result["typology"] is None and result["bedrooms"] is None and result["area_m2"] is None


def _import(source, root, run):
    return import_snapshot(load_catalog(), storage=LocalStorage(root), directory=source, snapshot_month="2025-08",
                           run_id=run, imported_at_utc="2026-11-13T12:00:00Z")


def _write(source, name, rows):
    source.mkdir(parents=True, exist_ok=True)
    path = source / name
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


def test_removed_file_changes_snapshot_and_empty_lists_remain_importable(tmp_path):
    source, root = tmp_path / "source", tmp_path / "lake"
    _write(source, "first.json", [])
    second = _write(source, "second.json", [])
    assert _import(source, root, "one")["status"] == "changed"
    second.unlink()
    assert _import(source, root, "two")["status"] == "changed"
    assert latest_snapshot(LocalStorage(root), "2025-08")["run_id"] == "two"


@pytest.mark.parametrize("rows", [{}, [None], [{"id": True}], [{"id": ""}],
                                  [{"id": "1", "Preco": [], "Titulo": "X", "tipologia": "T1", "areaBrutaM2": 1}]])
def test_malformed_input_never_becomes_current(tmp_path, rows):
    source, root = tmp_path / "source", tmp_path / "lake"
    _write(source, "bad.json", rows)
    with pytest.raises(IdealistaError):
        _import(source, root, "bad")
    assert latest_snapshot(LocalStorage(root), "2025-08") is None
    assert not (root / "raw").exists()


def test_unknown_source_or_overlapping_paths_are_rejected(tmp_path):
    source = tmp_path / "source"
    _write(source, "empty.json", [])
    with pytest.raises(CatalogError):
        import_snapshot({"sources": {}}, storage=LocalStorage(tmp_path / "other"), directory=source,
                        snapshot_month="2025-08", run_id="one", imported_at_utc="2026-11-13T12:00:00Z")
    with pytest.raises(IdealistaError, match="sobrepor"):
        _import(source, source / "destination", "overlap")
    assert list(source.rglob("*.json")) == [source / "empty.json"]


def test_latest_snapshot_compares_utc_instants_not_timestamp_spellings(tmp_path):
    source, root = tmp_path / "source", tmp_path / "lake"
    _write(source, "first.json", [])
    _import(source, root, "old")
    _write(source, "second.json", [])
    import_snapshot(load_catalog(), storage=LocalStorage(root), directory=source, snapshot_month="2025-08",
                    run_id="new", imported_at_utc="2026-11-13T12:00:00.500Z")
    assert latest_snapshot(LocalStorage(root), "2025-08")["run_id"] == "new"


def test_truncated_manifest_cannot_silently_drop_a_file(tmp_path):
    from tests.fixtures.idealista.ci_seed import seed

    root = tmp_path / "lake"
    result = seed(root, prepare=False)
    manifest_path = root / result["manifest_key"]
    result["files"].pop()
    manifest_path.write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(IdealistaError, match="manifest"):
        prepare_snapshot(root, tmp_path / "prepared", snapshot_month="2025-08", processed_at_utc="2026-11-13T12:00:00Z")
