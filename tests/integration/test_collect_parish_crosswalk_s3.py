"""A coleta da correspondência grava no S3 (moto) as mesmas chaves do modo local (spec 004, FR-017)."""

import json

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from pipelines.cli.collect_parish_crosswalk import main
from pipelines.collectors._shared.catalog import get_dataset_source, load_catalog
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors._shared.storage_s3 import S3Storage
from tests.fixtures.parish_crosswalk.tables import (
    make_table_a,
    make_table_b,
    offline_downloader,
)

BUCKET = "crosswalk-test-bucket"
SOURCE = get_dataset_source(load_catalog(), "ine_parish_crosswalk")
URL = {dataset["id"]: dataset["origin"] for dataset in SOURCE["datasets"]}


@pytest.fixture
def s3(monkeypatch):
    """Bucket simulado em memória; nenhuma conta ou credencial AWS real é tocada."""
    for name, value in {"AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test",
                        "AWS_DEFAULT_REGION": "eu-west-1"}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with mock_aws():
        client = boto3.client("s3")
        client.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "eu-west-1"})
        yield client


def _payloads(tmp_path):
    return {
        URL["reorganizacao_2013"]: make_table_a(tmp_path / "a.xlsx").read_bytes(),
        URL["reposicao_2025"]: make_table_b(tmp_path / "b.xlsx").read_bytes(),
    }


def _snapshot(storage):
    """Chaves e conteúdos com o run_id mascarado e sem horário, para comparar os destinos."""
    prefix = "manifests/ine_parish_crosswalk/"
    manifest_key = next(k for k in storage.list_keys() if k.startswith(prefix))
    run_id = manifest_key.removeprefix(prefix).removesuffix(".json")
    result = {}
    for key in storage.list_keys():
        content = storage.get(key)
        if key.startswith("manifests/"):
            manifest = json.loads(content.decode("utf-8").replace(run_id, "RUN"))
            manifest.pop("collected_at_utc")
            result[key.replace(run_id, "RUN")] = manifest
        else:
            result[key.replace(run_id, "RUN")] = content
    return result


def test_s3_and_local_have_the_same_keys_bytes_and_manifest(tmp_path, s3):
    pay = _payloads(tmp_path)
    assert main(["--local", "--root", str(tmp_path / "local")], downloader=offline_downloader(pay)) == 0
    argv = ["--s3", "--bucket", BUCKET, "--prefix", "/dev/", "--root", str(tmp_path / "work")]
    assert main(argv, downloader=offline_downloader(pay)) == 0
    local, remote = _snapshot(LocalStorage(tmp_path / "local")), _snapshot(S3Storage(BUCKET, "dev"))
    assert len(local) == 3 and remote == local  # 2 planilhas e 1 manifest
    stored = {item["Key"] for item in s3.list_objects_v2(Bucket=BUCKET)["Contents"]}
    assert all(key.startswith("dev/") for key in stored)


def test_denied_write_fails_before_any_download(tmp_path, s3, capsys):
    class DenyWrites(S3Storage):
        def put(self, key, content):
            raise ClientError({"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "PutObject")

    calls = []

    def forbidden(url, destination):
        calls.append(url)

    argv = ["--s3", "--bucket", BUCKET, "--root", str(tmp_path / "work")]
    assert main(argv, downloader=forbidden, storage=DenyWrites(BUCKET)) == 1
    assert "destino sem permissão" in capsys.readouterr().err
    assert calls == []
    assert S3Storage(BUCKET).list_keys() == set()
