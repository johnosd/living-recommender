"""Locked P1 contracts for the public CAOP collection boundary."""

import hashlib
import json

import pytest

from pipelines.collectors.caop.handler import CollectionError, collect_caop

URLS = {
    "continente": "https://example.test/continente.gpkg.zip",
    "acores": "https://example.test/acores.gpkg.zip",
    "madeira": "https://example.test/madeira.gpkg.zip",
}
PAYLOADS = {region: f"gpkg-{region}".encode() for region in URLS}
CATALOG = {
    "caop": {
        "version": "2025",
        "reference_period": "2025",
        "license_id": "CC-BY-4.0",
        "collection_method": "http_download",
        "urls": URLS,
    }
}


class MemoryStorage:
    def __init__(self):
        self.objects = {}

    def put(self, key, content):
        if key in self.objects:
            raise AssertionError(f"overwrite: {key}")
        self.objects[key] = content

    def put_file(self, key, path):
        self.put(key, path.read_bytes())

    def get(self, key):
        return self.objects[key]

    def delete(self, key):
        self.objects.pop(key, None)

    def list_keys(self):
        return set(self.objects)


def download(url, destination):
    region = next(region for region, configured in URLS.items() if configured == url)
    destination.write_bytes(PAYLOADS[region])


def validate(region, path):
    if path.read_bytes() != PAYLOADS[region]:
        raise ValueError(f"invalid {region}")


def run(storage, run_id, tmp_path, *, catalog=CATALOG, downloader=download, validator=validate):
    return collect_caop(
        catalog,
        storage=storage,
        downloader=downloader,
        validator=validator,
        run_id=run_id,
        collected_at_utc="2026-11-04T12:00:00Z",
        work_dir=tmp_path / run_id,
    )


def test_us1_ac1_fr004_fr005_changed_has_three_immutable_raw_files_and_manifest(tmp_path):
    storage = MemoryStorage()
    result = run(storage, "run-1", tmp_path)
    assert result["status"] == "changed"
    manifest = json.loads(storage.get("manifests/caop/run-1.json"))
    assert manifest["source_id"] == "caop"
    assert manifest["run_id"] == "run-1"
    assert manifest["status"] == "changed"
    assert manifest["reference_period"] == "2025"
    assert manifest["license_id"] == "CC-BY-4.0"
    assert manifest["collected_at_utc"] == "2026-11-04T12:00:00Z"
    assert len(manifest["files"]) == 3
    for region, payload in PAYLOADS.items():
        key = f"raw/source=caop/version=2025/run_id=run-1/{region}.gpkg.zip"
        assert storage.get(key) == payload
        entry = next(item for item in manifest["files"] if item["key"] == key)
        assert entry["sha256"] == hashlib.sha256(payload).hexdigest()
        assert entry["bytes"] == len(payload)


def test_us1_ac2_fr006_unchanged_writes_only_verification_manifest(tmp_path):
    storage = MemoryStorage()
    run(storage, "run-1", tmp_path)
    raw_before = {key for key in storage.list_keys() if key.startswith("raw/")}
    result = run(storage, "run-2", tmp_path)
    assert result["status"] == "unchanged"
    assert {key for key in storage.list_keys() if key.startswith("raw/")} == raw_before
    assert json.loads(storage.get("manifests/caop/run-2.json"))["status"] == "unchanged"


def test_us1_ac3_fr007_download_failure_leaves_no_raw_and_records_failed(tmp_path):
    storage = MemoryStorage()

    def failing_download(url, destination):
        if url == URLS["madeira"]:
            raise OSError("network interrupted")
        return download(url, destination)

    with pytest.raises(CollectionError):
        run(storage, "run-3", tmp_path, downloader=failing_download)
    assert not any(key.startswith("raw/") for key in storage.list_keys())
    assert json.loads(storage.get("manifests/caop/run-3.json"))["status"] == "failed"


def test_us1_ac4_fr008_invalid_region_is_not_committed(tmp_path):
    storage = MemoryStorage()

    def reject_madeira(region, path):
        if region == "madeira":
            raise ValueError("missing expected column: dicofre")
        validate(region, path)

    with pytest.raises(CollectionError):
        run(storage, "run-4", tmp_path, validator=reject_madeira)
    assert not any(key.startswith("raw/") for key in storage.list_keys())
    manifest = json.loads(storage.get("manifests/caop/run-4.json"))
    assert manifest["status"] == "failed"
    assert "dicofre" in manifest["error"]


def test_fr002_unknown_source_is_rejected_before_download(tmp_path):
    storage = MemoryStorage()
    called = False

    def forbidden_download(_url, _destination):
        nonlocal called
        called = True
        raise AssertionError("network must not be used")

    with pytest.raises(CollectionError):
        run(storage, "run-5", tmp_path, catalog={}, downloader=forbidden_download)
    assert called is False
    assert not any(key.startswith("raw/") for key in storage.list_keys())
