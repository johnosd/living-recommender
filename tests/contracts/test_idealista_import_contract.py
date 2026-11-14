"""Cinco contratos públicos da spec 005; todos os anúncios são sintéticos."""

import hashlib
import json

import pandas as pd
import pytest

from pipelines.collectors._shared.catalog import load_catalog
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors.idealista.prepare import prepare_snapshot
from pipelines.collectors.idealista.snapshot import IdealistaError, import_snapshot

MONTH = "2025-08"
NOW = "2026-11-13T12:00:00Z"


def listing(id="101", **changes):
    return {"id": id, "Titulo": "Apartamento, Bonfim", "Preco": "1.200,50€/mês",
            "tipologia": "T2", "areaBrutaM2": 80, **changes}


def write_file(directory, name, rows):
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return path


def import_run(directory, root, run="first", month=MONTH):
    return import_snapshot(load_catalog(), storage=LocalStorage(root), directory=directory,
                           snapshot_month=month, run_id=run, imported_at_utc=NOW)


def dimensions(root):
    for name, data in {
        "dim_municipality": {"dico": ["1312", "1106"], "official_name": ["Porto", "Lisboa"]},
        "dim_parish": {"dicofre": ["131203", "110601"], "dico": ["1312", "1106"],
                       "official_name": ["Bonfim", "Ajuda"]},
    }.items():
        path = root / "lake" / "silver" / name / "data.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(data).to_parquet(path, index=False)


def test_us1_raw_bytes_month_metadata_and_unchanged(tmp_path):
    source, root = tmp_path / "source", tmp_path / "lake"
    path = write_file(source, "norte/Porto-Paginas1.json", [listing()])
    original = path.read_bytes()
    result = import_run(source, root)
    assert result["status"] == "changed" and result["records"] == 1
    assert result["snapshot_month"] == MONTH and result["imported_at_utc"] == NOW
    assert result["collected_at_utc"] is None
    entry = result["files"][0]
    assert (root / entry["key"]).read_bytes() == original == path.read_bytes()
    assert entry["sha256"] == hashlib.sha256(original).hexdigest()
    repeated = import_run(source, root, "second")
    assert repeated["status"] == "unchanged" and repeated["source_run_id"] == "first"
    assert len(list((root / "raw").rglob("*.json"))) == 1
    assert import_run(source, root, "third", "2025-09")["status"] == "changed"


def test_fr004_invalid_later_file_does_not_commit_a_partial_batch(tmp_path):
    source, root = tmp_path / "source", tmp_path / "lake"
    write_file(source, "norte/Porto-Paginas1.json", [listing()])
    first = import_run(source, root)
    write_file(source, "z/bad.json", {"not": "a list"})
    with pytest.raises(IdealistaError):
        import_run(source, root, "bad")
    assert len(list((root / "raw").rglob("*.json"))) == 1
    failed = json.loads((root / "manifests/idealista/bad.json").read_text(encoding="utf-8"))
    assert failed["status"] == "failed"
    assert (root / first["files"][0]["key"]).exists()


def test_us2_us3_unique_rows_typed_values_and_regional_coverage(tmp_path):
    source, root, output = tmp_path / "source", tmp_path / "lake", tmp_path / "prepared"
    dimensions(root)
    write_file(source, "norte/Porto-Paginas1.json", [listing(), listing("102", Preco=None, areaBrutaM2=None)])
    write_file(source, "norte/Porto-Paginas2.json", [listing(Preco="1.500€/mês")])
    write_file(source, "Acores/arrendar-casas-acores-Paginas1.json", [listing("103", tipologia="T5")])
    import_run(source, root)
    result = prepare_snapshot(root, output, snapshot_month=MONTH, processed_at_utc=NOW)
    frame = pd.read_parquet(output / "listings.parquet").set_index("listing_id")
    assert result["records"] == 4 and result["unique_listings"] == 3 and result["duplicate_occurrences"] == 1
    assert frame.loc["101", "asking_rent_eur"] == 1200.5
    assert frame.loc["101", "duplicate_count"] == 1 and frame.loc["101", "has_conflict"]
    assert frame.loc["101", "dico"] == "1312" and frame.loc["101", "dicofre"] == "131203"
    assert pd.isna(frame.loc["102", "asking_rent_eur"]) and pd.isna(frame.loc["102", "area_m2"])
    assert frame.loc["103", "locality_level"] == "regiao" and pd.isna(frame.loc["103", "dico"])
    assert frame.loc["103", "typology"] == "T4+" and frame.loc["103", "bedrooms"] == 5
    assert len(pd.read_parquet(output / "occurrences.parquet")) == 4
    assert set(frame["snapshot_month"]) == {MONTH}
    assert frame["collected_at_utc"].isna().all()
    assert "agenciaNome" not in frame.columns and "Link" not in frame.columns


def test_fr007_unknown_municipality_is_not_silently_assigned(tmp_path):
    source, root = tmp_path / "source", tmp_path / "lake"
    dimensions(root)
    write_file(source, "norte/Desconhecido-Paginas1.json", [listing()])
    import_run(source, root)
    with pytest.raises(IdealistaError, match="município"):
        prepare_snapshot(root, tmp_path / "prepared", snapshot_month=MONTH, processed_at_utc=NOW)


def test_fr008_tampered_raw_is_rejected_before_processing(tmp_path):
    source, root = tmp_path / "source", tmp_path / "lake"
    dimensions(root)
    write_file(source, "norte/Porto-Paginas1.json", [listing()])
    result = import_run(source, root)
    (root / result["files"][0]["key"]).write_text("[]", encoding="utf-8")
    with pytest.raises(IdealistaError, match="checksum"):
        prepare_snapshot(root, tmp_path / "prepared", snapshot_month=MONTH, processed_at_utc=NOW)
