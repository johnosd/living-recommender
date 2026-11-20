import json
from copy import deepcopy

import pytest

from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors.wikipedia.handler import collect_wikipedia
from pipelines.collectors.wikipedia.manifest import digest
from tests.fixtures.wikipedia.responses import (
    associations,
    catalog,
    fetcher,
    municipalities,
)


def run(storage, tmp_path, run_id, fetch, **kwargs):
    return collect_wikipedia(catalog(), municipalities=municipalities(), associations=associations(),
        territory_hash=digest(b"dimension"), storage=storage, fetcher=fetch, run_id=run_id,
        collected_at_utc="2026-11-20T10:00:00Z", work_dir=tmp_path / "work" / run_id, **kwargs)


def test_wikipedia_local_storage_immutable_recovery_and_neighbor(tmp_path):
    storage = LocalStorage(tmp_path)
    storage.put("raw/source=other/data.json", b"neighbor")
    bad, _ = fetcher(failures={"0001"})
    first = run(storage, tmp_path, "first", bad)
    assert first["status"] == "partial"
    snapshot = {k: storage.get(k) for k in storage.list_keys()}
    good, _ = fetcher()
    second = run(storage, tmp_path, "second", good)
    assert second["status"] == "changed"
    assert all(storage.get(k) == v for k, v in snapshot.items())
    assert json.loads(storage.get(second["manifest_key"]))["territory_snapshot"] == municipalities()
    assert storage.get("raw/source=other/data.json") == b"neighbor"
    with pytest.raises(ValueError, match="já existe"):
        run(storage, tmp_path, "second", good)


def test_wikipedia_context_change_records_failed_attempt(tmp_path):
    storage = LocalStorage(tmp_path)
    fetch, _ = fetcher()
    result = run(storage, tmp_path, "changed_context", fetch, context_checker=lambda: False)
    assert result["status"] == "failed" and result["input_errors"]
    assert json.loads(storage.get(result["manifest_key"]))["status"] == "failed"


def test_wikipedia_resume_keeps_verification_dates_and_context(tmp_path):
    storage = LocalStorage(tmp_path)
    fetch, calls = fetcher()
    first = run(storage, tmp_path, "batch", fetch, max_municipalities=1)
    assert [e["status"] for e in first["entries"]] == ["changed", "pending"]
    resumed, calls = fetcher()
    second = run(storage, tmp_path, "resume", resumed, resume_manifest=first)
    assert [a["dico"] for a in calls] == ["0002"]
    assert second["entries"][0] == first["entries"][0]
    assert second["cycle_id"] == "batch" and second["parent_run_id"] == "batch"
    changed = deepcopy(first)
    changed["territory_hash"] = "changed"
    with pytest.raises(ValueError, match="contexto"):
        run(storage, tmp_path, "invalid_resume", resumed, resume_manifest=changed)
