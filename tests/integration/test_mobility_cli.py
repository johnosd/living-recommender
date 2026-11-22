"""CLI `collect_mobility` de ponta a ponta sobre disco e S3 simulado, mais o build (spec 009, US2 + US1)."""
import boto3
import httpx
import pandas as pd
from moto import mock_aws

from pipelines.cli import build_mobility
from pipelines.cli import collect_mobility as cli
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors._shared.storage_s3 import S3Storage
from tests.fixtures.mobility.ci_seed import seed
from tests.fixtures.mobility.responses import KEY_SENTINEL, routes_ok

ENV = {"GOOGLE_ROUTES_API_KEY": KEY_SENTINEL}


def ok_client(calls=None):
    def handler(request):
        if calls is not None:
            calls.append(1)
        return httpx.Response(200, content=routes_ok().encode(), headers={"content-type": "application/json"})

    return httpx.Client(transport=httpx.MockTransport(handler))


def args(root, *extra):
    return ["--local", "--root", str(root), "--catalog", str(root / "catalog.yml"), "--poles", str(root / "poles.yml"),
            *extra]


def test_estimate_then_execute_then_nothing_left_and_the_build_sees_every_pair(tmp_path, capsys):
    seed(tmp_path)
    calls = []
    assert cli.main(args(tmp_path), client=ok_client(calls), env={}, sleep=lambda s: None) == 0
    assert "total: 10" in capsys.readouterr().out and not calls
    execute = args(tmp_path, "--execute", "--confirm-elements", "10")
    assert cli.main(execute, client=ok_client(calls), env=ENV, sleep=lambda s: None) == 0
    out = capsys.readouterr()
    assert len(calls) == 10 and "gravados: 10" in out.out and KEY_SENTINEL not in out.out + out.err
    assert len(LocalStorage(tmp_path).list_keys("raw/")) == 10
    calls.clear()
    assert cli.main(args(tmp_path, "--execute", "--confirm-elements", "0"), client=ok_client(calls), env=ENV,
                    sleep=lambda s: None) == 0
    assert "nada a coletar" in capsys.readouterr().out and not calls  # SC-005/SC-006: nothing is queried again
    result = build_mobility.build_mobility(tmp_path, catalog=seed_catalog(tmp_path), poles_path=tmp_path / "poles.yml")
    frame = pd.read_parquet(tmp_path / "lake/bronze/stg_municipality_pole_distance/data.parquet")
    assert set(frame[frame["mode"] != "straight_line"]["status"]) == {"ok"} and result["rows"] == 36
    assert frame[(frame["mode"] == "driving") & (frame["pole_id"] == "aeroporto_x")]["km"].round(3).tolist() == [12.0] * 3


def seed_catalog(root):
    from pipelines.collectors._shared.catalog import load_catalog

    return load_catalog(root / "catalog.yml")


def test_ctrl_c_keeps_the_progress_and_a_rerun_only_queries_the_pending_pairs(tmp_path, capsys):
    seed(tmp_path)
    calls = []

    def interrupted(item, destination):
        if len(calls) == 4:
            raise KeyboardInterrupt
        calls.append(item["id"])
        destination.write_text(routes_ok(), encoding="utf-8")

    execute = args(tmp_path, "--execute", "--confirm-elements", "10")
    assert cli.main(execute, fetcher=interrupted, env=ENV, sleep=lambda s: None) == 2
    assert "pendentes: 6" in capsys.readouterr().out and len(LocalStorage(tmp_path).list_keys("raw/")) == 4
    done = list(calls)
    calls.clear()
    resume = args(tmp_path, "--execute", "--confirm-elements", "6")
    assert cli.main(resume, client=ok_client(calls), env=ENV, sleep=lambda s: None) == 0
    assert len(calls) == 6 and len(LocalStorage(tmp_path).list_keys("raw/")) == 10 and len(done) == 4


def test_local_and_s3_have_identical_keys_and_bytes(tmp_path, monkeypatch):
    for name, value in {"AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test",
                        "AWS_DEFAULT_REGION": "eu-west-1"}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setattr(cli, "new_run_id", lambda: "same-run")
    monkeypatch.setattr(cli, "utc_now", lambda: "2026-11-21T12:00:00Z")
    seed(tmp_path)
    execute = ("--execute", "--confirm-elements", "10")
    with mock_aws():
        boto3.client("s3").create_bucket(Bucket="mobility-test",
                                         CreateBucketConfiguration={"LocationConstraint": "eu-west-1"})
        assert cli.main(args(tmp_path, *execute), client=ok_client(), env=ENV, sleep=lambda s: None) == 0
        s3_args = ["--s3", "--bucket", "mobility-test", "--prefix", "dev", "--root", str(tmp_path),
                   "--catalog", str(tmp_path / "catalog.yml"), "--poles", str(tmp_path / "poles.yml"), *execute]
        assert cli.main(s3_args, client=ok_client(), env=ENV, sleep=lambda s: None) == 0
        local, remote = LocalStorage(tmp_path), S3Storage("mobility-test", "dev")
        keys = local.list_keys("raw/") | local.list_keys("manifests/")
        assert keys == remote.list_keys() and len(keys) == 11
        assert all(local.get(key) == remote.get(key) for key in keys)


def test_bad_configuration_is_reported_in_portuguese_with_exit_code_one(tmp_path, capsys):
    seed(tmp_path)
    (tmp_path / "poles.yml").write_text("version: 1\npoles: []\n", encoding="utf-8")
    assert cli.main(args(tmp_path), env={}) == 1
    assert "Mobilidade: falha" in capsys.readouterr().err
    assert cli.main(["--local", "--root", str(tmp_path / "vazio")], env={}) == 1  # no silver, no catalog override
