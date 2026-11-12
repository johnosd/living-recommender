"""Checagem do primeiro bloco por formato (CSV, JSON e o ZIP padrão da CAOP)."""

import httpx
import pytest

from pipelines.collectors._shared.http import (
    DownloadError,
    HttpDownloader,
    RateLimiter,
    csv_content_check,
    json_content_check,
    xlsx_content_check,
)


def _download(tmp_path, body, *, content_type="text/csv", check=csv_content_check, headers=None):
    def respond(request):
        return httpx.Response(200, content=body, headers={"content-type": content_type, **(headers or {})},
                              request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        downloader = HttpDownloader(client=client, rate_limiter=RateLimiter(0), content_check=check)
        destination = tmp_path / "arquivo"
        downloader("https://example.test/arquivo", destination)
        return downloader, destination


def test_csv_is_accepted_and_cache_headers_are_recorded(tmp_path):
    downloader, destination = _download(
        tmp_path, b"01. Ano,Valor\n2024,1\n",
        headers={"etag": "0x8DE0", "last-modified": "Mon, 20 Oct 2025 14:05:28 GMT"},
    )
    assert destination.read_bytes().startswith(b"01. Ano")
    assert downloader.last_headers == {"etag": "0x8DE0", "last_modified": "Mon, 20 Oct 2025 14:05:28 GMT"}


@pytest.mark.parametrize(
    ("body", "content_type"),
    [
        (b"<html><body>erro</body></html>", "text/html"),
        (b"<!DOCTYPE html><html></html>", "text/csv"),  # HTML servido como CSV
        (b"  <html>", "application/octet-stream"),
    ],
)
def test_csv_check_rejects_html_pages_without_leaving_a_file(tmp_path, body, content_type):
    with pytest.raises(DownloadError, match="HTML"):
        _download(tmp_path, body, content_type=content_type)
    assert not (tmp_path / "arquivo").exists()
    assert not list(tmp_path.glob(".download-*"))


def test_json_check_accepts_objects_and_lists_and_rejects_everything_else(tmp_path):
    _download(tmp_path, b'[{"IndicadorCod": "1"}]', content_type="application/json", check=json_content_check)
    other = tmp_path / "outro"
    other.mkdir()
    _download(other, b'{"a": 1}', content_type="application/json", check=json_content_check)
    for body, content_type, message in [
        (b"<html></html>", "text/html", "HTML"),
        (b"Erro interno", "application/json", "JSON"),
    ]:
        failing = tmp_path / message
        failing.mkdir()
        with pytest.raises(DownloadError, match=message):
            _download(failing, body, content_type=content_type, check=json_content_check)


def test_xlsx_check_accepts_a_zip_container_and_rejects_html_and_other_files(tmp_path):
    ok = tmp_path / "ok"
    ok.mkdir()
    _, destination = _download(
        ok, b"PK\x03\x04conteudo", content_type="application/octet-stream", check=xlsx_content_check,
    )
    assert destination.read_bytes().startswith(b"PK")
    for body, content_type, message in [
        (b"<html><body>erro</body></html>", "text/html", "HTML"),
        (b"<!DOCTYPE html><html></html>", "application/octet-stream", "HTML"),
        (b"a,b\n1,2\n", "application/octet-stream", "xlsx"),
    ]:
        failing = tmp_path / message
        failing.mkdir(exist_ok=True)
        with pytest.raises(DownloadError, match=message):
            _download(failing, body, content_type=content_type, check=xlsx_content_check)
        assert not (failing / "arquivo").exists()


def test_default_check_is_still_zip_so_the_caop_downloader_is_unchanged(tmp_path):
    def respond(request):
        return httpx.Response(200, content=b"not a zip", headers={"content-type": "application/zip"},
                              request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        downloader = HttpDownloader(client=client, rate_limiter=RateLimiter(0))
        with pytest.raises(DownloadError, match="ZIP"):
            downloader("https://example.test/a.zip", tmp_path / "a.zip")
