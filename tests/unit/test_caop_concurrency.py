import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import httpx
import pytest

from pipelines.collectors._shared.catalog import get_source, load_catalog
from pipelines.collectors._shared.http import HttpDownloader, RateLimiter
from pipelines.collectors._shared.manifest import latest_changed
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors.caop.handler import CollectionError, collect_caop

TIME = "2026-11-04T12:00:00Z"
CATALOG = load_catalog()
SOURCE = get_source(CATALOG)


def _run(tmp_path, storage, run_id, downloader):
    return collect_caop(
        CATALOG,
        storage=storage,
        downloader=downloader,
        validator=lambda _region, _path: None,
        run_id=run_id,
        collected_at_utc=TIME,
        work_dir=tmp_path / "work" / run_id,
    )


def test_concurrent_runs_keep_separate_prefixes_and_complete_manifests(tmp_path):
    storage = LocalStorage(tmp_path / "lake")
    barrier = Barrier(2)
    first_url = SOURCE["urls"]["continente"]

    def download(url, destination):
        if url == first_url:
            barrier.wait(timeout=5)
        destination.write_bytes(b"PK\x03\x04" + url.encode())

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(_run, tmp_path, storage, run_id, download) for run_id in ("a", "b")]
        results = [future.result() for future in futures]
    assert {result["run_id"] for result in results} == {"a", "b"}
    assert all(result["status"] in {"changed", "unchanged"} for result in results)
    changed = [result for result in results if result["status"] == "changed"]
    assert changed
    for result in changed:
        manifest = json.loads(storage.get(result["manifest_key"]))
        assert len(manifest["files"]) == 3
        for entry in manifest["files"]:
            assert storage.get(entry["key"]).startswith(b"PK\x03\x04")
    assert latest_changed(storage)["run_id"] in {result["run_id"] for result in changed}


def test_exhausted_http_retry_records_failed_and_preserves_prior_raw(tmp_path):
    storage = LocalStorage(tmp_path / "lake")

    def download(url, destination):
        destination.write_bytes(b"PK\x03\x04" + url.encode())

    assert _run(tmp_path, storage, "prior", download)["status"] == "changed"
    raw_before = {key: storage.get(key) for key in storage.list_keys() if key.startswith("raw/")}
    attempts = []

    def unavailable(request):
        attempts.append(request)
        return httpx.Response(503, request=request)

    with httpx.Client(transport=httpx.MockTransport(unavailable)) as client:
        retrying = HttpDownloader(
            client=client, max_attempts=2, backoff=0,
            rate_limiter=RateLimiter(0), sleep=lambda _seconds: None,
        )
        with pytest.raises(CollectionError, match="download"):
            _run(tmp_path, storage, "failed", retrying)
    assert len(attempts) == 2
    assert {key: storage.get(key) for key in raw_before} == raw_before
    assert latest_changed(storage)["run_id"] == "prior"
    failed = json.loads(storage.get("manifests/caop/failed.json"))
    assert failed["status"] == "failed"
    assert _run(tmp_path, storage, "same", download)["status"] == "unchanged"
