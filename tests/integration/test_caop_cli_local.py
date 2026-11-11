import json

from pipelines.cli.collect_caop import main
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors.caop.schema import validate_caop_archive
from tests.fixtures.caop.build import make_archive, make_archives, offline_downloader


def test_cli_local_changed_then_unchanged_without_network(tmp_path, capsys):
    archives = make_archives(tmp_path / "fixtures")
    root = tmp_path / "lake"
    download = offline_downloader(archives)
    argv = ["--local", "--root", str(root)]
    assert main(argv, downloader=download, validator=validate_caop_archive) == 0
    output = capsys.readouterr().out
    assert "changed" in output and "manifest:" in output
    storage = LocalStorage(root)
    raw_before = {key for key in storage.list_keys() if key.startswith("raw/")}
    assert len(raw_before) == 3
    assert main([*argv, "--force-check"], downloader=download, validator=validate_caop_archive) == 0
    assert "unchanged" in capsys.readouterr().out
    assert {key for key in storage.list_keys() if key.startswith("raw/")} == raw_before
    manifests = [json.loads(storage.get(key)) for key in storage.list_keys() if key.startswith("manifests/")]
    assert {manifest["status"] for manifest in manifests} == {"changed", "unchanged"}


def test_cli_invalid_geo_package_has_failed_manifest_and_no_raw(tmp_path, capsys):
    archives = {
        region: make_archive(region, tmp_path / "fixtures", invalid_parish=region == "madeira")
        for region in ("continente", "acores", "madeira")
    }
    root = tmp_path / "lake"
    assert main(
        ["--local", "--root", str(root)],
        downloader=offline_downloader(archives),
        validator=validate_caop_archive,
    ) == 1
    assert "código territorial inválido" in capsys.readouterr().err
    storage = LocalStorage(root)
    assert not any(key.startswith("raw/") for key in storage.list_keys())
    manifests = [json.loads(storage.get(key)) for key in storage.list_keys() if key.startswith("manifests/")]
    assert len(manifests) == 1 and manifests[0]["status"] == "failed"
