"""CLI de coleta da correspondência de freguesias em destino local, sem rede (spec 004, US1)."""

import json

import pytest

from pipelines.cli.collect_parish_crosswalk import main
from pipelines.collectors._shared.catalog import get_dataset_source, load_catalog
from pipelines.collectors._shared.http import DownloadError
from pipelines.collectors._shared.storage import LocalStorage
from tests.fixtures.parish_crosswalk.tables import (
    ROWS_B,
    make_table_a,
    make_table_b,
    offline_downloader,
)

SOURCE = get_dataset_source(load_catalog(), "ine_parish_crosswalk")
URL = {dataset["id"]: dataset["origin"] for dataset in SOURCE["datasets"]}


def _payloads(tmp_path, *, rows_b=None):
    return {
        URL["reorganizacao_2013"]: make_table_a(tmp_path / "a.xlsx").read_bytes(),
        URL["reposicao_2025"]: make_table_b(tmp_path / "b.xlsx", rows_b).read_bytes(),
    }


def _raw(storage):
    return {key for key in storage.list_keys() if key.startswith("raw/")}


def _manifests(storage):
    return [json.loads(storage.get(k)) for k in sorted(storage.list_keys()) if k.startswith("manifests/")]


def test_changed_then_unchanged_then_only_the_altered_table_is_written(tmp_path, capsys):
    root, pay = tmp_path / "lake", _payloads(tmp_path)
    argv = ["--local", "--root", str(root)]

    assert main(argv, downloader=offline_downloader(pay)) == 0
    out = capsys.readouterr().out
    assert "Correspondência INE: changed" in out and "reorganizacao_2013: changed" in out
    storage = LocalStorage(root)
    first = _raw(storage)
    assert len(first) == 2 and all(key.endswith(".xlsx") for key in first)

    assert main(argv, downloader=offline_downloader(pay)) == 0
    assert "Correspondência INE: unchanged" in capsys.readouterr().out
    assert _raw(storage) == first  # SC-003: nenhum bruto novo

    # Só a B é regerada. Regerar a A mudaria seus bytes (o openpyxl grava a hora de criação, com resolução de
    # segundos), e o teste falharia sempre que as duas gerações caíssem em segundos diferentes.
    changed_b = make_table_b(tmp_path / "b2.xlsx", [*ROWS_B, ("090103", "Tres", "Junta", "090151", "Tres")])
    altered = {**pay, URL["reposicao_2025"]: changed_b.read_bytes()}
    assert main(argv, downloader=offline_downloader(altered)) == 0
    new = _raw(storage) - first
    assert len(new) == 1 and "dataset=reposicao_2025/" in next(iter(new))
    states = {e["dataset_id"]: e["status"] for e in _manifests(storage)[-1]["datasets"]}
    assert states == {"reorganizacao_2013": "unchanged", "reposicao_2025": "changed"}


def test_a_failing_table_gives_exit_code_1_without_blocking_the_other(tmp_path, capsys):
    root, pay = tmp_path / "lake", _payloads(tmp_path)
    pay[URL["reorganizacao_2013"]] = b"<html><body>erro</body></html>"
    assert main(["--local", "--root", str(root)], downloader=offline_downloader(pay)) == 1
    out = capsys.readouterr().out
    assert "Correspondência INE: partial" in out and "reorganizacao_2013: failed" in out
    storage = LocalStorage(root)
    assert len(_raw(storage)) == 1 and "dataset=reposicao_2025/" in next(iter(_raw(storage)))
    assert _manifests(storage)[0]["status"] == "partial"


def test_a_download_error_in_one_table_is_isolated(tmp_path, capsys):
    root, pay = tmp_path / "lake", _payloads(tmp_path)
    inner = offline_downloader(pay)

    def flaky(url, destination):
        if url == URL["reposicao_2025"]:
            raise DownloadError("download falhou após 3 tentativa(s)")
        return inner(url, destination)

    assert main(["--local", "--root", str(root)], downloader=flaky) == 1
    out = capsys.readouterr().out
    assert "reposicao_2025: failed" in out and "download falhou" in out
    assert len(_raw(LocalStorage(root))) == 1


def test_s3_without_bucket_is_a_usage_error(tmp_path):
    with pytest.raises(SystemExit) as error:
        main(["--s3", "--root", str(tmp_path)], downloader=offline_downloader({}))
    assert error.value.code == 2


def test_a_catalog_without_the_source_fails_before_any_download(tmp_path, capsys):
    catalog = tmp_path / "vazio.yml"
    catalog.write_text("sources:\n  outra:\n    id: outra\n", encoding="utf-8")
    calls = []

    def forbidden(url, destination):
        calls.append(url)

    code = main(["--local", "--root", str(tmp_path / "lake"), "--catalog", str(catalog)], downloader=forbidden)
    assert code == 1 and calls == []
    assert "Correspondência INE: falha" in capsys.readouterr().err
