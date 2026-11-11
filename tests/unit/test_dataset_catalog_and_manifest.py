"""Catálogo de datasets e manifest v2 (spec 002): validação e estado vigente por dataset."""

import json

import pytest

from pipelines.collectors._shared.catalog import (
    CatalogError,
    get_dataset_source,
    load_catalog,
)
from pipelines.collectors._shared.dataset_manifest import (
    DatasetManifestError,
    encode_dataset_manifest,
    latest_dataset_states,
    make_dataset_manifest,
    run_status,
)
from pipelines.collectors._shared.storage import LocalStorage

SHA = "a" * 64


def _source(**overrides):
    source = {
        "license_id": "CC-BY-4.0",
        "collection_method": "http_download",
        "name_column": "Nome",
        "datasets": [{"id": "d1", "origin": "https://example.test/d1.csv"}],
    }
    source.update(overrides)
    return {"sources": {"fonte": source}}


def test_dataset_source_inherits_source_defaults_and_method():
    source = get_dataset_source(_source(), "fonte")
    assert source["datasets"][0]["collection_method"] == "http_download"
    assert source["datasets"][0]["name_column"] == "Nome"


@pytest.mark.parametrize(
    ("catalog", "message"),
    [
        ({"sources": {}}, "não cadastrada"),
        (_source(datasets=[]), "sem datasets"),
        (_source(datasets=[{"origin": "https://example.test/x.csv"}]), "sem id"),
        (_source(datasets=[{"id": "d1", "origin": "https://example.test/a"},
                           {"id": "d1", "origin": "https://example.test/b"}]), "repetido"),
        (_source(datasets=[{"id": "d1", "origin": "http://example.test/a.csv"}]), "HTTPS"),
        (_source(collection_method="api_json", datasets=[{"id": "d1"}]), "indicator"),
        (_source(collection_method="ftp"), "método não suportado"),
        (_source(license_id=""), "license_id"),
    ],
)
def test_dataset_source_rejects_invalid_catalogs_before_any_network(catalog, message):
    with pytest.raises(CatalogError, match=message):
        get_dataset_source(catalog, "fonte")


def test_manual_upload_dataset_needs_no_origin():
    catalog = _source(datasets=[{"id": "planilha", "collection_method": "manual_upload"}])
    assert get_dataset_source(catalog, "fonte")["datasets"][0]["id"] == "planilha"


def test_real_catalog_declares_pordata_and_ine_datasets():
    catalog = load_catalog()
    pordata = get_dataset_source(catalog, "pordata", strict_metadata=True)
    ine = get_dataset_source(catalog, "ine", strict_metadata=True)
    methods = [dataset["collection_method"] for dataset in pordata["datasets"]]
    assert methods.count("http_download") == 16 and methods.count("manual_upload") == 1
    assert [dataset["indicator"] for dataset in ine["datasets"]] == ["0014698", "0008074", "0014580"]
    assert ine["datasets"][1]["params"]["Dim3"] == "T,1,2,3,4,5,6"
    assert pordata["license_id"] == "not_granted_by_source"


def _entry(dataset_id, status="changed", run="r1", error=None):
    if status == "failed":
        return {"dataset_id": dataset_id, "status": "failed", "key": None, "error": error or "falhou"}
    entry = {
        "dataset_id": dataset_id, "status": status,
        "key": f"raw/source=fonte/dataset={dataset_id}/run_id={run}/{dataset_id}.csv",
        "sha256": SHA, "bytes": 10, "fingerprint": SHA,
    }
    if status == "unchanged":
        entry["previous_changed_run_id"] = "r0"
    return entry


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (["changed", "unchanged"], "changed"),
        (["unchanged", "unchanged"], "unchanged"),
        (["changed", "failed"], "partial"),
        (["unchanged", "failed"], "partial"),
        (["failed", "failed"], "failed"),
    ],
)
def test_run_status_is_derived_from_each_dataset(statuses, expected):
    entries = [{"dataset_id": f"d{index}", "status": status} for index, status in enumerate(statuses)]
    assert run_status(entries) == expected


def test_manifest_rejects_bad_run_id_time_and_entries():
    source = {"license_id": "x", "collection_method": "http_download"}
    ok = {"source_id": "fonte", "run_id": "r1", "collected_at_utc": "2026-11-11T12:00:00Z",
          "datasets": [_entry("d1")]}
    assert make_dataset_manifest(source, **ok)["schema_version"] == 2
    with pytest.raises(DatasetManifestError, match="run_id"):
        make_dataset_manifest(source, **{**ok, "run_id": "a/b"})
    with pytest.raises(DatasetManifestError, match="UTC"):
        make_dataset_manifest(source, **{**ok, "collected_at_utc": "2026-11-11T12:00:00+01:00"})
    with pytest.raises(DatasetManifestError, match="erro"):
        make_dataset_manifest(source, **{**ok, "datasets": [{"dataset_id": "d1", "status": "failed"}]})
    with pytest.raises(DatasetManifestError, match="checksum"):
        make_dataset_manifest(source, **{**ok, "datasets": [{**_entry("d1"), "sha256": "curto"}]})


def _store(storage, run, when, entries, source_id="fonte", schema_version=2):
    source = {"license_id": "x", "collection_method": "http_download"}
    manifest = make_dataset_manifest(source, source_id=source_id, run_id=run, collected_at_utc=when,
                                     datasets=entries)
    manifest["schema_version"] = schema_version
    storage.put(f"manifests/{source_id}/{run}.json", encode_dataset_manifest(manifest))


def test_state_is_independent_per_dataset_and_failed_or_unchanged_never_count(tmp_path):
    storage = LocalStorage(tmp_path / "root")
    _store(storage, "r1", "2026-11-11T10:00:00Z", [_entry("d1", run="r1"), _entry("d2", run="r1")])
    _store(storage, "r2", "2026-11-11T11:00:00Z",
           [_entry("d1", "failed"), _entry("d2", "unchanged", run="r1")])
    _store(storage, "r3", "2026-11-11T12:00:00Z", [_entry("d1", run="r3"), _entry("d3", "failed")])
    states = latest_dataset_states(storage, "fonte")
    assert set(states) == {"d1", "d2"}
    assert states["d1"]["run_id"] == "r3" and states["d2"]["run_id"] == "r1"


def test_partial_manifest_provides_state_for_the_datasets_that_succeeded(tmp_path):
    storage = LocalStorage(tmp_path / "root")
    _store(storage, "r1", "2026-11-11T10:00:00Z", [_entry("d1", run="r1"), _entry("d2", "failed")])
    assert json.loads(storage.get("manifests/fonte/r1.json"))["status"] == "partial"
    assert set(latest_dataset_states(storage, "fonte")) == {"d1"}


def test_same_time_is_resolved_by_run_id_and_other_sources_or_versions_are_ignored(tmp_path):
    storage = LocalStorage(tmp_path / "root")
    _store(storage, "r1", "2026-11-11T10:00:00Z", [_entry("d1", run="r1")])
    _store(storage, "r2", "2026-11-11T10:00:00Z", [_entry("d1", run="r2")])
    _store(storage, "x1", "2026-11-11T13:00:00Z", [_entry("d1", run="x1")], source_id="outra")
    storage.put("manifests/fonte/legado.json", json.dumps({"schema_version": 1, "source_id": "fonte"}).encode())
    states = latest_dataset_states(storage, "fonte")
    assert states["d1"]["run_id"] == "r2"


def test_run_collection_method_is_the_one_all_datasets_share_or_mixed():
    """Regressão da carga manual: o método da fonte (`http_download`) não descreve um dataset `manual_upload`."""
    source = {"license_id": "x", "collection_method": "http_download"}
    common = {"source_id": "fonte", "run_id": "r1", "collected_at_utc": "2026-11-11T12:00:00Z"}
    manual = {**_entry("d1"), "collection_method": "manual_upload"}
    http = {**_entry("d2"), "collection_method": "http_download"}
    assert make_dataset_manifest(source, datasets=[manual], **common)["collection_method"] == "manual_upload"
    assert make_dataset_manifest(source, datasets=[http], **common)["collection_method"] == "http_download"
    assert make_dataset_manifest(source, datasets=[manual, http], **common)["collection_method"] == "mixed"
    # entradas sem o campo (manifests anteriores): vale o método da fonte
    assert make_dataset_manifest(source, datasets=[_entry("d3")], **common)["collection_method"] == "http_download"
