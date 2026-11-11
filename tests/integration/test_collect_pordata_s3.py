"""O coletor do Pordata grava no S3 (simulado pelo moto) as mesmas chaves do modo local (SC-005)."""

import json

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from pipelines.cli.collect_pordata import main
from pipelines.collectors._shared.catalog import get_dataset_source, load_catalog
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors._shared.storage_s3 import S3Storage
from tests.fixtures.pordata.layouts import offline_downloader, pordata_csv

BUCKET = "pordata-test-bucket"
HTTP = [d for d in get_dataset_source(load_catalog(), "pordata")["datasets"] if d["collection_method"] == "http_download"]


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


def _snapshot(storage):
    """Chaves e conteúdos com o run_id mascarado e sem horário, para comparar os destinos."""
    manifest_key = next(k for k in storage.list_keys() if k.startswith("manifests/pordata/"))
    run_id = manifest_key.removeprefix("manifests/pordata/").removesuffix(".json")
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


def _downloader():
    return offline_downloader({d["origin"]: pordata_csv("a") for d in HTTP})


def test_sc005_s3_and_local_have_the_same_keys_bytes_and_manifest(tmp_path, s3):
    assert main(["--local", "--root", str(tmp_path / "local")], downloader=_downloader()) == 0
    argv = ["--s3", "--bucket", BUCKET, "--prefix", "/dev/", "--root", str(tmp_path / "work")]
    assert main(argv, downloader=_downloader()) == 0
    local = _snapshot(LocalStorage(tmp_path / "local"))
    remote = _snapshot(S3Storage(BUCKET, "dev"))
    assert len(local) == 17  # 16 CSV e 1 manifest
    assert remote == local
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


def test_sc005_ine_also_matches_the_local_destination(tmp_path, s3):
    from pipelines.cli.collect_ine import main as collect_ine_main
    from pipelines.collectors.ine.fetch import build_url
    from tests.fixtures.ine.responses import ine_response

    datasets = get_dataset_source(load_catalog(), "ine")["datasets"]
    texts = {build_url(d): ine_response(d["indicator"]) for d in datasets}
    assert collect_ine_main(["--local", "--root", str(tmp_path / "local")], downloader=offline_downloader(texts)) == 0
    argv = ["--s3", "--bucket", BUCKET, "--root", str(tmp_path / "work")]
    assert collect_ine_main(argv, downloader=offline_downloader(texts)) == 0

    def snapshot(storage):
        manifest_key = next(k for k in storage.list_keys() if k.startswith("manifests/ine/"))
        run_id = manifest_key.removeprefix("manifests/ine/").removesuffix(".json")
        result = {}
        for key in storage.list_keys():
            content = storage.get(key).decode("utf-8").replace(run_id, "RUN")
            parsed = json.loads(content) if key.startswith("manifests/") else content
            if key.startswith("manifests/"):
                parsed.pop("collected_at_utc")
            result[key.replace(run_id, "RUN")] = parsed
        return result

    local, remote = snapshot(LocalStorage(tmp_path / "local")), snapshot(S3Storage(BUCKET))
    assert len(local) == 4 and remote == local  # 3 indicadores e 1 manifest


def test_sc005_manual_upload_also_matches_the_local_destination(tmp_path, s3):
    from pipelines.cli.load_pordata_manual import main as manual_main
    from tests.fixtures.pordata.xlsx import make_pordata_xlsx

    source = make_pordata_xlsx(tmp_path / "poder.xlsx", [f"Município {n:03d}" for n in range(308)])
    assert manual_main(["--local", "--root", str(tmp_path / "local"), "--file", str(source)]) == 0
    argv = ["--s3", "--bucket", BUCKET, "--root", str(tmp_path / "work"), "--file", str(source)]
    assert manual_main(argv) == 0

    def snapshot(storage):
        manifest_key = next(k for k in storage.list_keys() if k.startswith("manifests/pordata/"))
        run_id = manifest_key.removeprefix("manifests/pordata/").removesuffix(".json")
        result = {}
        for key in storage.list_keys():
            content = storage.get(key)
            if key.startswith("manifests/"):
                parsed = json.loads(content.decode("utf-8").replace(run_id, "RUN"))
                parsed.pop("collected_at_utc")
                content = parsed
            result[key.replace(run_id, "RUN")] = content
        return result

    local, remote = snapshot(LocalStorage(tmp_path / "local")), snapshot(S3Storage(BUCKET))
    assert len(local) == 2 and remote == local  # a planilha e o manifest
    assert source.read_bytes() == next(v for k, v in local.items() if k.startswith("raw/"))
