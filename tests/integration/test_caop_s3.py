"""US3: o mesmo coletor grava no S3 (simulado pelo moto) com as mesmas chaves do modo local."""

import json

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from pipelines.cli.collect_caop import main
from pipelines.collectors._shared.storage import InvalidKey, LocalStorage
from pipelines.collectors._shared.storage_s3 import S3Storage
from pipelines.collectors.caop.schema import validate_caop_archive
from tests.fixtures.caop.build import make_archives, offline_downloader

BUCKET = "caop-test-bucket"
RAW = "raw/source=caop/version=2025/run_id={}/continente.gpkg.zip"


@pytest.fixture
def s3(monkeypatch):
    """Bucket simulado em memória; nenhuma conta ou credencial AWS real é tocada."""
    for name, value in {
        "AWS_ACCESS_KEY_ID": "test",
        "AWS_SECRET_ACCESS_KEY": "test",
        "AWS_DEFAULT_REGION": "eu-west-1",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with mock_aws():
        client = boto3.client("s3")
        client.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "eu-west-1"})
        yield client


def _snapshot(storage):
    """Chaves e conteúdos com o run_id mascarado e sem horários, para comparar destinos."""
    manifest_key = next(key for key in storage.list_keys() if key.startswith("manifests/caop/"))
    run_id = manifest_key.removeprefix("manifests/caop/").removesuffix(".json")
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


def _s3_args(tmp_path, *extra):
    return ["--s3", "--bucket", BUCKET, "--root", str(tmp_path / "work"), *extra]


def test_us3_ac1_s3_and_local_have_same_keys_bytes_and_manifest(tmp_path, s3):
    download = offline_downloader(make_archives(tmp_path / "zips"))
    local_root = tmp_path / "local"
    assert main(
        ["--local", "--root", str(local_root)], downloader=download, validator=validate_caop_archive
    ) == 0
    assert main(_s3_args(tmp_path), downloader=download, validator=validate_caop_archive) == 0

    local, remote = _snapshot(LocalStorage(local_root)), _snapshot(S3Storage(BUCKET))
    assert len(local) == 4  # três ZIPs e um manifest
    assert remote == local


def test_s3_prefix_keeps_all_objects_under_it(tmp_path, s3, capsys):
    download = offline_downloader(make_archives(tmp_path / "zips"))
    assert main(
        _s3_args(tmp_path, "--prefix", "/ambiente/dev/"),
        downloader=download,
        validator=validate_caop_archive,
    ) == 0
    assert "s3://caop-test-bucket/ambiente/dev" in capsys.readouterr().out
    stored = {item["Key"] for item in s3.list_objects_v2(Bucket=BUCKET)["Contents"]}
    assert len(stored) == 4 and all(key.startswith("ambiente/dev/") for key in stored)
    assert len(S3Storage(BUCKET, "ambiente/dev").list_keys()) == 4


def test_us3_ac2_denied_write_fails_before_any_download(tmp_path, s3, capsys):
    class DenyWrites(S3Storage):
        def put(self, key, content):
            raise ClientError({"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "PutObject")

    downloads = []

    def forbidden(url, destination):
        downloads.append(url)

    assert main(
        _s3_args(tmp_path), downloader=forbidden, validator=validate_caop_archive,
        storage=DenyWrites(BUCKET),
    ) == 1
    err = capsys.readouterr().err
    assert "destino sem permissão" in err and "AccessDenied" in err
    assert downloads == []
    assert S3Storage(BUCKET).list_keys() == set()


def test_us3_ac2_missing_bucket_fails_before_any_download(tmp_path, s3, capsys):
    downloads = []
    argv = ["--s3", "--bucket", "bucket-que-nao-existe", "--root", str(tmp_path / "work")]
    assert main(
        argv, downloader=lambda url, destination: downloads.append(url), validator=validate_caop_archive
    ) == 1
    assert "destino sem permissão ou inacessível" in capsys.readouterr().err
    assert downloads == []


def test_us3_ac3_local_mode_never_creates_an_aws_client(tmp_path, monkeypatch):
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_PROFILE"):
        monkeypatch.delenv(name, raising=False)

    def no_aws(*args, **kwargs):
        raise AssertionError("o modo local não pode usar o SDK da AWS")

    monkeypatch.setattr(boto3, "client", no_aws)
    download = offline_downloader(make_archives(tmp_path / "zips"))
    assert main(
        ["--local", "--root", str(tmp_path / "lake")], downloader=download, validator=validate_caop_archive
    ) == 0


def test_s3_upload_failure_cleans_the_run_and_rerun_is_idempotent(tmp_path, s3, capsys):
    class InterruptedUpload(S3Storage):
        uploads = 0

        def put_file(self, key, source):
            self.uploads += 1
            if self.uploads == 2:
                raise OSError("upload interrompido")
            super().put_file(key, source)

    download = offline_downloader(make_archives(tmp_path / "zips"))
    assert main(
        _s3_args(tmp_path), downloader=download, validator=validate_caop_archive,
        storage=InterruptedUpload(BUCKET),
    ) == 1
    assert "gravação raw" in capsys.readouterr().err
    remaining = S3Storage(BUCKET).list_keys()
    assert not any(key.startswith("raw/") for key in remaining)
    (manifest_key,) = remaining
    assert json.loads(S3Storage(BUCKET).get(manifest_key))["status"] == "failed"

    for expected in ("changed", "unchanged"):
        assert main(_s3_args(tmp_path), downloader=download, validator=validate_caop_archive) == 0
        assert expected in capsys.readouterr().out
    raw = {key for key in S3Storage(BUCKET).list_keys() if key.startswith("raw/")}
    assert len(raw) == 3


def test_s3_cli_requires_bucket_and_rejects_bucket_without_s3(tmp_path, capsys):
    for argv in (["--s3"], ["--bucket", BUCKET], ["--local", "--s3", "--bucket", BUCKET]):
        with pytest.raises(SystemExit) as exit_info:
            main(argv)
        assert exit_info.value.code == 2
    assert "--bucket" in capsys.readouterr().err


def test_s3_storage_never_overwrites_and_keeps_relative_keys(tmp_path, s3):
    storage = S3Storage(BUCKET, "env")
    first, second = RAW.format("one"), RAW.format("two")
    storage.put(first, b"original")
    with pytest.raises(FileExistsError):
        storage.put(first, b"novo")
    source = tmp_path / "source.zip"
    source.write_bytes(b"conteudo")
    with pytest.raises(FileExistsError):
        storage.put_file(first, source)
    assert storage.get(first) == b"original"

    storage.put_file(second, source)
    assert storage.list_keys() == {first, second}
    assert storage.list_keys("raw/source=caop/version=2025/run_id=two/") == {second}
    storage.delete_prefix("raw/source=caop/version=2025/run_id=two/")
    assert storage.list_keys() == {first}

    storage.preflight()
    assert storage.list_keys() == {first}  # a prova de escrita não deixa objeto para trás
    with pytest.raises(InvalidKey):
        storage.put("../escape", b"x")
    with pytest.raises(InvalidKey):
        storage.delete_prefix("raw/")
    with pytest.raises(FileNotFoundError):
        storage.get("raw/ausente")
