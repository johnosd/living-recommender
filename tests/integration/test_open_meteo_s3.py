import boto3
from moto import mock_aws

from pipelines.cli import collect_open_meteo as cli
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors._shared.storage_s3 import S3Storage
from tests.integration.test_open_meteo_cli_local import offline, write_silver


def test_local_and_s3_have_identical_keys_bytes_and_manifest(tmp_path, monkeypatch):
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'test')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'test')
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'eu-west-1')
    monkeypatch.delenv('AWS_PROFILE', raising=False)
    monkeypatch.setattr(cli, 'new_run_id', lambda: 'same-run')
    monkeypatch.setattr(cli, 'utc_now', lambda: '2026-11-11T12:00:00Z')
    write_silver(tmp_path)
    with mock_aws():
        client = boto3.client('s3')
        client.create_bucket(Bucket='climate-test', CreateBucketConfiguration={'LocationConstraint': 'eu-west-1'})
        assert cli.main(['--local', '--root', str(tmp_path)], fetcher=offline) == 0
        assert cli.main(['--s3', '--bucket', 'climate-test', '--prefix', 'dev', '--root', str(tmp_path)],
                        fetcher=offline) == 0
        local, remote = LocalStorage(tmp_path), S3Storage('climate-test', 'dev')
        keys = local.list_keys('raw/') | local.list_keys('manifests/')
        assert keys == remote.list_keys()
        assert len(keys) == 309
        assert all(local.get(key) == remote.get(key) for key in keys)
