"""Importação local e S3 simulado, sem acesso ao Idealista ou a conta AWS real."""

import json

import boto3
from moto import mock_aws

from pipelines.cli.import_idealista_snapshot import main
from pipelines.collectors._shared.catalog import load_catalog
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors._shared.storage_s3 import S3Storage
from pipelines.collectors.idealista.snapshot import import_snapshot


def test_manual_import_has_the_same_bytes_and_manifest_on_local_and_simulated_s3(tmp_path, monkeypatch):
    for name, value in {"AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test", "AWS_DEFAULT_REGION": "eu-west-1"}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    source = tmp_path / "source"
    source.mkdir()
    payload = json.dumps([{"id": "synthetic", "Titulo": "Apartamento, Bonfim", "Preco": "900€/mês",
                           "tipologia": "T1", "areaBrutaM2": 40}], ensure_ascii=False).encode("utf-8")
    (source / "Porto-Paginas1.json").write_bytes(payload)
    options = {"directory": source, "snapshot_month": "2025-08", "run_id": "one", "imported_at_utc": "2026-11-13T12:00:00Z"}
    local = LocalStorage(tmp_path / "local")
    expected = import_snapshot(load_catalog(), storage=local, **options)
    with mock_aws():
        client = boto3.client("s3")
        client.create_bucket(Bucket="idealista-test", CreateBucketConfiguration={"LocationConstraint": "eu-west-1"})
        remote = S3Storage("idealista-test")
        actual = import_snapshot(load_catalog(), storage=remote, **options)
        assert actual == expected
        assert remote.get(actual["files"][0]["key"]) == payload
        assert remote.get(actual["manifest_key"]) == local.get(expected["manifest_key"])
        repeated = import_snapshot(load_catalog(), storage=remote, **{**options, "run_id": "two"})
        assert repeated["status"] == "unchanged" and repeated["source_run_id"] == "one"


def test_cli_rejects_destination_under_source_without_creating_it(tmp_path, capsys):
    source = tmp_path / "source"
    source.mkdir()
    (source / "Porto.json").write_text("[]", encoding="utf-8")
    destination = source / "destination"
    assert main(["--directory", str(source), "--snapshot-month", "2025-08", "--root", str(destination)]) == 1
    assert not destination.exists()
    assert "sobrepor" in capsys.readouterr().err
