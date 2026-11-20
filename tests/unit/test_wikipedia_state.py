import pytest

from pipelines.collectors.wikipedia.manifest import (
    digest,
    read_manifests,
    validate_run_id,
)
from pipelines.collectors.wikipedia.state import fingerprint, indexes, store_roles
from tests.fixtures.open_meteo.responses import MemoryStorage
from tests.fixtures.wikipedia.responses import associations, documents


def test_wikipedia_canonical_hash_and_semantic_fingerprint():
    assert digest({"b": 1, "a": 2}) == digest({"a": 2, "b": 1})
    meta, parsed = documents()
    initial = fingerprint(meta, parsed, associations()[0], "territory")
    meta["warnings"] = {"operational": "deprecated"}
    assert fingerprint(meta, parsed, associations()[0], "territory") == initial
    parsed["parse"]["text"] += " changed rendered template"
    assert fingerprint(meta, parsed, associations()[0], "territory") != initial


@pytest.mark.parametrize("value", ["../bad", "a/b", "a\\b", "", "..", "a.json", "x:y"])
def test_wikipedia_rejects_unsafe_run_paths(value):
    with pytest.raises(ValueError):
        validate_run_id(value)


def test_wikipedia_role_reuse_verifies_old_bytes_and_ignores_orphans():
    storage = MemoryStorage()
    payloads = {"metadata": b"meta", "content": b"html"}
    first = store_roles(storage, payloads, None, "0001", "one", "date")
    storage.put("raw/source=wikipedia/orphan.json", b"orphan")
    assert read_manifests(storage) == []
    second = store_roles(storage, {**payloads, "content": b"newhtml"}, {"files": first}, "0001", "two", "date2")
    assert second[0] == first[0] and second[1]["run_id"] == "two"
    broken = [dict(first[0], sha256="broken"), first[1]]
    with pytest.raises(ValueError, match="checksum"):
        store_roles(storage, payloads, {"files": broken}, "0001", "three", "date3")


def test_wikipedia_last_failed_never_erases_valid_content_or_absence():
    first = {"dico": "0001", "status": "changed", "revision_id": 1}
    absent = {"dico": "0002", "status": "absent", "absence_evidence": {"reviewer": "curator"}}
    failed = dict(first, status="failed", error="network")
    valid, latest = indexes([{"entries": [first, absent]}, {"entries": [failed]}])
    assert valid["0001"] == first and latest["0001"] == failed
    assert valid["0002"] == absent
