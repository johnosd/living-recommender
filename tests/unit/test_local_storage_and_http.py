import os
from pathlib import Path

import httpx
import pytest

from pipelines.collectors._shared.http import DownloadError, HttpDownloader, RateLimiter
from pipelines.collectors._shared.storage import InvalidKey, LocalStorage

ZIP_BYTES = b"PK\x03\x04synthetic-archive"


def test_storage_preserves_original_and_removes_only_current_run(tmp_path):
    storage = LocalStorage(tmp_path / "root")
    key = "raw/source=caop/version=2025/run_id=one/continente.gpkg.zip"
    other = "raw/source=caop/version=2025/run_id=two/continente.gpkg.zip"
    storage.put(key, ZIP_BYTES)
    with pytest.raises(FileExistsError):
        storage.put(key, b"replacement")
    assert storage.get(key) == ZIP_BYTES
    source = tmp_path / "source.zip"
    source.write_bytes(b"second")
    storage.put_file(other, source)
    assert storage.get(other) == b"second"
    assert not list((tmp_path / "root").rglob(".object-*"))
    storage.delete_prefix("raw/source=caop/version=2025/run_id=two/")
    assert key in storage.list_keys()
    assert other not in storage.list_keys()
    with pytest.raises(InvalidKey):
        storage.put("../escape", b"bad")


@pytest.mark.skipif(os.name != "nt", reason="prefixo estendido é específico do Windows")
def test_storage_accepts_same_windows_path_with_extended_prefix(tmp_path, monkeypatch):
    storage = LocalStorage(tmp_path / "root")
    original_resolve = Path.resolve

    def resolve_with_windows_prefix(path, *args, **kwargs):
        resolved = original_resolve(path, *args, **kwargs)
        if path.name == "b.json":
            return Path("\\\\?\\" + str(resolved))
        return resolved

    monkeypatch.setattr(Path, "resolve", resolve_with_windows_prefix)
    storage.put("manifests/caop/b.json", b"{}")
    assert storage.get("manifests/caop/b.json") == b"{}"


def test_http_retries_timeout_and_server_error_with_backoff(tmp_path):
    attempts = []
    delays = []

    def respond(request):
        attempts.append(request)
        if len(attempts) == 1:
            raise httpx.ReadTimeout("timed out", request=request)
        if len(attempts) == 2:
            return httpx.Response(503, request=request)
        return httpx.Response(200, content=ZIP_BYTES, request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        download = HttpDownloader(
            client=client,
            max_attempts=3,
            backoff=0.5,
            rate_limiter=RateLimiter(0),
            sleep=delays.append,
        )
        destination = tmp_path / "file.zip"
        assert download("https://example.test/file.zip", destination) == destination
    assert destination.read_bytes() == ZIP_BYTES
    assert delays == [0.5, 1.0]
    assert all("living-recommender" in req.headers["User-Agent"] for req in attempts)
    assert not list(tmp_path.glob(".download-*"))


def test_html_is_rejected_without_committing_file(tmp_path):
    def respond(request):
        return httpx.Response(
            200, content=b"<html>error</html>", headers={"content-type": "text/html"}, request=request
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        download = HttpDownloader(client=client, rate_limiter=RateLimiter(0))
        with pytest.raises(DownloadError, match="HTML"):
            download("https://example.test/file.zip", tmp_path / "file.zip")
    assert not (tmp_path / "file.zip").exists()
    assert not list(tmp_path.glob(".download-*"))


def test_rate_limiter_waits_between_requests():
    now = [0.0]
    delays = []

    def advance(delay):
        delays.append(delay)
        now[0] += delay

    limiter = RateLimiter(2.0, clock=lambda: now[0], sleep=advance)
    limiter.wait()
    limiter.wait()
    assert delays == [2.0]


def test_put_file_failure_leaves_no_partial_object(tmp_path):
    storage = LocalStorage(tmp_path / "root")
    key = "raw/source=caop/version=2025/run_id=one/madeira.gpkg.zip"
    with pytest.raises(FileNotFoundError):
        storage.put_file(key, Path(tmp_path / "absent.zip"))
    assert key not in storage.list_keys()
    assert not list((tmp_path / "root").rglob(".object-*"))
