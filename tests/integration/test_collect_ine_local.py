"""CLI/handler do INE em destino local, sem rede (US2)."""

import json

from pipelines.cli.collect_ine import main
from pipelines.collectors._shared.catalog import get_dataset_source, load_catalog
from pipelines.collectors._shared.http import DownloadError
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors.ine.fetch import build_url
from tests.fixtures.ine.responses import CRIME_CATEGORIES, ine_response
from tests.fixtures.pordata.layouts import offline_downloader

DATASETS = {d["id"]: d for d in get_dataset_source(load_catalog(), "ine")["datasets"]}


def _texts(extracted_at="2026-11-11T18:00:00.000Z", **overrides):
    texts = {}
    for dataset_id, dataset in DATASETS.items():
        options = {"categories": CRIME_CATEGORIES} if dataset_id == "taxa_criminalidade" else {}
        texts[build_url(dataset)] = ine_response(
            dataset["indicator"], extracted_at=extracted_at, **options, **overrides.get(dataset_id, {})
        )
    return texts


def _url(dataset_id):
    return build_url(DATASETS[dataset_id])


def _raw(storage):
    return {key for key in storage.list_keys() if key.startswith("raw/")}


def _last_manifest(storage):
    return json.loads(storage.get(max(k for k in storage.list_keys() if k.startswith("manifests/"))))


def test_us2_changed_then_unchanged_when_only_the_extraction_time_differs(tmp_path, capsys):
    root = tmp_path / "lake"
    argv = ["--local", "--root", str(root)]
    assert main(argv, downloader=offline_downloader(_texts())) == 0
    storage = LocalStorage(root)
    raw_first = _raw(storage)
    assert len(raw_first) == 3 and all(key.endswith(".json") for key in raw_first)
    assert "INE: changed" in capsys.readouterr().out

    assert main(argv, downloader=offline_downloader(_texts("2026-11-11T22:30:00.000Z"))) == 0
    assert "INE: unchanged" in capsys.readouterr().out
    assert _raw(storage) == raw_first

    altered = _texts("2026-11-12T08:00:00.000Z", rendas_novos_contratos={"value_offset": 1.5})
    assert main(argv, downloader=offline_downloader(altered)) == 0
    new = _raw(storage) - raw_first
    assert len(new) == 1 and "dataset=rendas_novos_contratos/" in next(iter(new))


def test_manifest_records_reference_period_and_release_date_from_the_response(tmp_path):
    root = tmp_path / "lake"
    assert main(["--local", "--root", str(root)], downloader=offline_downloader(_texts())) == 0
    entry = {e["dataset_id"]: e for e in _last_manifest(LocalStorage(root))["datasets"]}["rendas_novos_contratos"]
    assert entry["reference_period"] == "2025" and entry["source_release_date"] == "2026-09-29"
    assert _last_manifest(LocalStorage(root))["license_id"] == "CC-BY-4.0"


def test_a_failing_indicator_gives_partial_and_exit_code_1_without_blocking_the_others(tmp_path, capsys):
    root, texts = tmp_path / "lake", _texts()
    texts[_url("poder_compra_per_capita")] = json.dumps([{"IndicadorCod": "0014580", "Sucesso": {}}])
    failing = {_url("taxa_criminalidade"): DownloadError("download falhou após 3 tentativa(s): timed out")}
    code = main(["--local", "--root", str(root)], downloader=offline_downloader(texts, failing=failing))
    assert code == 1
    out = capsys.readouterr().out
    assert "INE: partial" in out and "taxa_criminalidade: failed" in out and "poder_compra_per_capita: failed" in out
    storage = LocalStorage(root)
    assert len(_raw(storage)) == 1 and "dataset=rendas_novos_contratos/" in next(iter(_raw(storage)))
    assert not list(root.rglob(".object-*"))
