"""Comando local e S3 simulado; nenhuma conexão INE/AWS real."""

import json

import boto3
import pytest
import yaml
from moto import mock_aws

from pipelines.cli.collect_censos import main
from pipelines.collectors._shared.datasets import DatasetCollectionError
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors._shared.storage_s3 import S3Storage
from pipelines.collectors.censos2021.handler import collect_censos
from tests.fixtures.censos2021.responses import catalog, downloader
from tests.fixtures.open_meteo.responses import MemoryStorage


def test_batch_repeat_ignores_extraction_time_and_row_order_without_new_raw(tmp_path):
    from tests.fixtures.censos2021.ci_seed import fixture_catalog, fixture_downloader

    storage = LocalStorage(tmp_path / "root")
    options = {"storage": storage, "collected_at_utc": "2026-11-13T12:00:00Z"}
    first = collect_censos(
        fixture_catalog(),
        downloader=fixture_downloader,
        run_id="first",
        work_dir=tmp_path / "first",
        **options,
    )
    raw_before = {
        k: storage.get(k) for k in storage.list_keys() if k.startswith("raw/")
    }

    def reordered(url, path):
        fixture_downloader(url, path)
        docs = json.loads(path.read_text("utf8"))
        docs[0]["DataExtracao"] = "2027-01-01T00:00:00Z"
        if "Dados" in docs[0]:
            docs[0]["Dados"]["2021"].reverse()
        path.write_text(json.dumps(docs), encoding="utf8")

    second = collect_censos(
        fixture_catalog(),
        downloader=reordered,
        run_id="second",
        work_dir=tmp_path / "second",
        **options,
    )
    assert first["status"] == "changed" and second["status"] == "unchanged"
    assert len(second["datasets"]) == 6
    assert {
        k: storage.get(k) for k in storage.list_keys() if k.startswith("raw/")
    } == raw_before


def test_cli_local_bytes_release_dates_and_repeat(tmp_path):
    path = tmp_path / "catalog.yml"
    path.write_text(yaml.safe_dump(catalog()), encoding="utf8")
    args = ["--local", "--root", str(tmp_path / "lake"), "--catalog", str(path)]
    assert main(args, downloader=downloader()) == 0
    assert main(args, downloader=downloader()) == 0
    storage = LocalStorage(tmp_path / "lake")
    manifests = [
        json.loads(storage.get(k))
        for k in storage.list_keys()
        if k.startswith("manifests/")
    ]
    assert {m["status"] for m in manifests} == {"changed", "unchanged"}
    first = next(m for m in manifests if m["status"] == "changed")
    assert all(e["source_release_date"] for e in first["datasets"])
    with pytest.raises(SystemExit):
        main(["--s3"])


def test_manifest_failure_cleans_only_new_raw_and_run_id_cannot_repeat(tmp_path):
    class Broken(MemoryStorage):
        def put(self, key, value):
            if key.startswith("manifests/"):
                raise OSError("denied")
            super().put(key, value)

    storage = Broken()
    with pytest.raises(DatasetCollectionError, match="manifest"):
        collect_censos(
            catalog(),
            storage=storage,
            downloader=downloader(),
            run_id="x",
            collected_at_utc="2026-11-13T12:00:00Z",
            work_dir=tmp_path / "work",
        )
    assert not storage.list_keys()
    storage = MemoryStorage()
    args = {
        "storage": storage,
        "downloader": downloader(),
        "run_id": "x",
        "collected_at_utc": "2026-11-13T12:00:00Z",
        "work_dir": tmp_path / "ok",
    }
    collect_censos(catalog(), **args)
    with pytest.raises(DatasetCollectionError, match="run_id"):
        collect_censos(catalog(), **args)


def test_s3_moto_matches_local_layout(tmp_path, monkeypatch):
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        monkeypatch.setenv(k, "test")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        boto3.client("s3").create_bucket(Bucket="censos-test")
        storage = S3Storage("censos-test", "fixture")
        result = collect_censos(
            catalog(),
            storage=storage,
            downloader=downloader(),
            run_id="test",
            collected_at_utc="2026-11-13T12:00:00Z",
            work_dir=tmp_path / "work",
        )
        assert result["status"] == "changed"
        assert len(storage.list_keys()) == 4
