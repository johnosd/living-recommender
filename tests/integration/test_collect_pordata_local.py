"""CLI/handler do Pordata em destino local, sem rede (US1)."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from pipelines.cli.collect_pordata import main
from pipelines.collectors._shared.catalog import get_dataset_source, load_catalog
from pipelines.collectors._shared.http import DownloadError
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors.pordata.handler import collect_pordata
from tests.fixtures.pordata.layouts import offline_downloader, pordata_csv

CATALOG = load_catalog()
HTTP = [d for d in get_dataset_source(CATALOG, "pordata")["datasets"] if d["collection_method"] == "http_download"]
LAYOUTS = ("a", "b", "c")


def _texts():
    return {d["origin"]: pordata_csv(LAYOUTS[i % 3]) for i, d in enumerate(HTTP)}


def _url(dataset_id):
    return next(d["origin"] for d in HTTP if d["id"] == dataset_id)


def _raw(storage):
    return {key for key in storage.list_keys() if key.startswith("raw/")}


def _manifests(storage):
    return [json.loads(storage.get(k)) for k in sorted(storage.list_keys()) if k.startswith("manifests/")]


def test_us1_changed_then_unchanged_then_only_the_altered_dataset_is_written(tmp_path, capsys):
    root, texts = tmp_path / "lake", _texts()
    argv = ["--local", "--root", str(root)]
    assert main(argv, downloader=offline_downloader(texts)) == 0
    storage = LocalStorage(root)
    raw_first = _raw(storage)
    assert len(raw_first) == 16
    assert "Pordata: changed" in capsys.readouterr().out

    assert main(argv, downloader=offline_downloader(texts)) == 0
    assert "Pordata: unchanged" in capsys.readouterr().out
    assert _raw(storage) == raw_first

    texts[_url("farmacias")] = pordata_csv("a", value_offset=5)
    assert main(argv, downloader=offline_downloader(texts)) == 0
    new = _raw(storage) - raw_first
    assert len(new) == 1 and "dataset=farmacias/" in next(iter(new))
    entries = {e["dataset_id"]: e["status"] for e in _manifests(storage)[-1]["datasets"]}
    assert entries.pop("farmacias") == "changed" and set(entries.values()) == {"unchanged"}


def test_manual_dataset_is_not_collected_by_the_http_command(tmp_path):
    storage = LocalStorage(tmp_path / "lake")
    assert main(["--local", "--root", str(tmp_path / "lake")], downloader=offline_downloader(_texts())) == 0
    manifest = _manifests(storage)[0]
    ids = {e["dataset_id"] for e in manifest["datasets"]}
    assert len(ids) == 16 and "poder_compra_per_capita_xlsx" not in ids
    assert manifest["collection_method"] == "http_download"
    assert {e["collection_method"] for e in manifest["datasets"]} == {"http_download"}


def test_a_failing_dataset_gives_partial_and_exit_code_1_without_blocking_the_others(tmp_path, capsys):
    root, texts = tmp_path / "lake", _texts()
    texts[_url("farmacias")] = "<html><body>erro</body></html>"
    failing = {_url("hospitais"): DownloadError("resposta HTML no lugar de CSV")}
    code = main(["--local", "--root", str(root)], downloader=offline_downloader(texts, failing=failing))
    assert code == 1
    out = capsys.readouterr().out
    assert "Pordata: partial" in out
    assert "hospitais: failed" in out and "farmacias: failed" in out and "HTML" in out
    storage = LocalStorage(root)
    assert len(_raw(storage)) == 14
    assert not any("farmacias" in key or "hospitais" in key for key in _raw(storage))
    assert not list((root).rglob(".object-*"))
    assert _manifests(storage)[0]["status"] == "partial"


def test_fr002_source_missing_from_the_catalog_is_refused_before_any_download(tmp_path, capsys):
    catalog = yaml.safe_load(Path("config/sources.yml").read_text(encoding="utf-8"))
    del catalog["sources"]["pordata"]
    path = tmp_path / "sem_pordata.yml"
    path.write_text(yaml.safe_dump(catalog, allow_unicode=True), encoding="utf-8")
    calls = []

    def forbidden(url, destination):
        calls.append(url)

    assert main(["--local", "--root", str(tmp_path / "lake"), "--catalog", str(path)], downloader=forbidden) == 1
    assert "não cadastrada" in capsys.readouterr().err
    assert calls == []


def test_two_concurrent_runs_do_not_corrupt_each_other_and_the_next_run_is_unchanged(tmp_path):
    storage = LocalStorage(tmp_path / "lake")
    texts = _texts()

    def run(run_id):
        return collect_pordata(
            CATALOG, storage=storage, downloader=offline_downloader(texts), run_id=run_id,
            collected_at_utc="2026-11-11T12:00:00Z", work_dir=tmp_path / "work" / run_id,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(run, ["run-a", "run-b"]))
    assert first["status"] == "changed" and second["status"] == "changed"
    assert not list((tmp_path / "lake").rglob(".object-*"))
    assert len(_raw(storage)) == 32  # cada execução grava o seu próprio prefixo
    assert {m["run_id"] for m in _manifests(storage)} == {"run-a", "run-b"}

    third = run("run-c")
    assert third["status"] == "unchanged"
    assert len(_raw(storage)) == 32
