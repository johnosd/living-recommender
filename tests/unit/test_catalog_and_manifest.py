import hashlib
import json

import pytest

from pipelines.collectors._shared.catalog import CatalogError, get_source, load_catalog
from pipelines.collectors._shared.manifest import (
    file_digest,
    latest_changed,
    make_manifest,
    same_checksums,
)
from pipelines.collectors._shared.storage import LocalStorage


def test_catalog_requires_registered_source_and_complete_metadata():
    catalog = load_catalog()
    source = get_source(catalog)
    assert source["publisher"] == "Direção-Geral do Território"
    assert source["license_id"] == "CC-BY-4.0"
    assert source["version"] == "2025"
    assert set(source["urls"]) == {"continente", "acores", "madeira"}
    with pytest.raises(CatalogError, match="não cadastrada"):
        get_source(catalog, "outra")
    incomplete = {"sources": {"caop": {"id": "caop", "urls": source["urls"]}}}
    with pytest.raises(CatalogError, match="sem campos"):
        get_source(incomplete)


def test_digest_and_latest_changed_ignore_failed_and_unchanged(tmp_path):
    source = get_source(load_catalog())
    storage = LocalStorage(tmp_path / "lake")
    files = []
    for region in source["urls"]:
        path = tmp_path / f"{region}.zip"
        payload = f"PK-{region}".encode()
        path.write_bytes(payload)
        entry = file_digest(
            path, key=f"raw/source=caop/version=2025/run_id=one/{region}.gpkg.zip", region=region
        )
        assert entry["sha256"] == hashlib.sha256(payload).hexdigest()
        assert entry["bytes"] == len(payload)
        files.append(entry)
    changed = make_manifest(
        source, run_id="one", collected_at_utc="2026-11-04T12:00:00Z", status="changed", files=files
    )
    assert changed["source_url"] == source["urls"]
    assert changed["version"] == "2025"
    assert changed["reference_period"] == "2025"
    older_files = [{**entry, "key": entry["key"].replace("run_id=one", "run_id=zero")} for entry in files]
    older = make_manifest(
        source,
        run_id="zero",
        collected_at_utc="2026-11-03T12:00:00Z",
        status="changed",
        files=older_files,
    )
    storage.put("manifests/caop/zero.json", json.dumps(older).encode())
    storage.put("manifests/caop/one.json", json.dumps(changed).encode())
    for status, run_id in (("unchanged", "two"), ("failed", "three")):
        manifest = make_manifest(
            source,
            run_id=run_id,
            collected_at_utc="2026-11-05T12:00:00Z",
            status=status,
            error="network" if status == "failed" else None,
            previous_changed_run_id="one",
        )
        storage.put(f"manifests/caop/{run_id}.json", json.dumps(manifest).encode())
    assert latest_changed(storage)["run_id"] == "one"
    assert same_checksums(files, latest_changed(storage))
    modified = [{**files[0], "sha256": "0" * 64}, *files[1:]]
    assert not same_checksums(modified, latest_changed(storage))
