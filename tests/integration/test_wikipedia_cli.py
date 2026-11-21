import json
from datetime import UTC, datetime, timedelta

import pytest

from pipelines.cli.collect_wikipedia import main
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors.wikipedia.fetch import PendingFetch, SourceBlocked
from pipelines.collectors.wikipedia.handler import collect_wikipedia
from pipelines.collectors.wikipedia.manifest import read_manifests
from tests.fixtures.wikipedia.ci_seed import seed
from tests.fixtures.wikipedia.responses import (
    associations,
    catalog,
    documents,
    encode,
    fetcher,
    municipalities,
)


def arguments(root):
    return ["--local", "--root", str(root), "--catalog", str(root / "catalog.yml"),
            "--associations", str(root / "associations.csv")]


def test_wikipedia_cli_batch_and_resume(tmp_path, capsys):
    root = tmp_path / "fixture"
    seed(root)
    fetch, _calls = fetcher()
    assert main(arguments(root) + ["--max-municipalities", "1"], fetcher=fetch) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["counts"] == {"unchanged": 1, "pending": 1}
    resumed, resumed_calls = fetcher()
    assert main(arguments(root) + ["--resume-run-id", result["run_id"]], fetcher=resumed) == 0
    assert len(resumed_calls) == 1 and resumed_calls[0]["dico"] == "0002"
    manifests = read_manifests(LocalStorage(root))
    assert manifests[-1]["entries"][0] == manifests[-2]["entries"][0]


def test_wikipedia_cli_invalid_contact_and_mismatched_context_before_network(tmp_path, capsys):
    root = tmp_path / "fixture"
    seed(root)
    fetch, calls = fetcher()
    assert main(arguments(root) + ["--contact", "anonymous"], fetcher=fetch) == 1
    assert not calls
    assert main(arguments(root) + ["--contact", "https://example.test/project", "--resume-run-id", "fixture"], fetcher=fetch) == 1
    assert not calls


@pytest.mark.parametrize("case,code", [("interrupt", 2), ("long_wait", 2), ("blocked", 1)])
def test_wikipedia_cli_stops_source_and_records_pending(tmp_path, case, code):
    root = tmp_path / "fixture"
    seed(root)
    calls = []

    def fail(association):
        calls.append(association["dico"])
        if case == "interrupt":
            raise KeyboardInterrupt()
        if case == "long_wait":
            raise PendingFetch("wait", (datetime.now(UTC) + timedelta(hours=1)).isoformat())
        raise SourceBlocked("blocked")

    assert main(arguments(root), fetcher=fail) == code
    manifest = read_manifests(LocalStorage(root))[-1]
    assert len(calls) == 1 and manifest["entries"][1]["status"] == "pending"
    if case == "long_wait":
        fetch, retried = fetcher()
        assert main(arguments(root) + ["--resume-run-id", manifest["run_id"]], fetcher=fetch) == 1
        assert not retried


def test_wikipedia_same_revision_render_changed_and_single_role_reused(tmp_path):
    root = tmp_path / "fixture"
    previous = seed(root)
    meta, parsed = documents()
    parsed["parse"]["text"] = parsed["parse"]["text"].replace("Primeiro parágrafo", "Conteúdo atualizado do primeiro parágrafo")
    fetch, calls = fetcher(overrides={"0001": (meta, parsed)})
    result = collect_wikipedia(catalog(), municipalities=municipalities(), associations=associations(),
        territory_hash=previous["territory_hash"], storage=LocalStorage(root), fetcher=fetch, run_id="new-render",
        collected_at_utc="2026-11-20T12:00:00Z", work_dir=root / "work-new")
    assert len(calls) == 2
    first, second = result["entries"]
    assert first["status"] == "changed" and second["status"] == "unchanged"
    assert first["revision_id"] == previous["entries"][0]["revision_id"]
    assert first["files"][0] == previous["entries"][0]["files"][0]
    assert first["files"][1]["key"] != previous["entries"][0]["files"][1]["key"]


def test_wikipedia_cli_sigint_deferred_until_manifest_checkpoint(tmp_path):
    import signal

    root = tmp_path / "fixture"
    seed(root)
    calls = []

    def signal_after_response(association):
        calls.append(association["dico"])
        meta, parsed = documents(association)
        signal.raise_signal(signal.SIGINT)
        return {"metadata": encode(meta), "content": encode(parsed)}

    previous_handler = signal.getsignal(signal.SIGINT)
    assert main(arguments(root), fetcher=signal_after_response) == 2
    assert signal.getsignal(signal.SIGINT) == previous_handler
    latest = read_manifests(LocalStorage(root))[-1]
    assert len(calls) == 1
    assert [e["status"] for e in latest["entries"]] == ["unchanged", "pending"]
    assert latest["entries"][1]["reason"] == "interrupted"
