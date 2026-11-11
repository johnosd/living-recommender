"""Locked P1 contracts for per-dataset ingestion (spec 002: Pordata and INE).

Only the public boundaries are exercised: `collect_datasets`, `fingerprint_ine_response`
and `resolve_municipality_names`, with injected fetcher/validator/storage and no network.
"""

import hashlib
import json

import pytest

from pipelines.collectors._shared.datasets import collect_datasets
from pipelines.collectors._shared.municipality import (
    UnresolvedMunicipalities,
    resolve_municipality_names,
)
from pipelines.collectors.ine.fingerprint import fingerprint_ine_response

CATALOG = {
    "pordata": {
        "license_id": "not_granted_by_source",
        "collection_method": "http_download",
        "datasets": [
            {"id": "d1", "origin": "https://example.test/d1.csv"},
            {"id": "d2", "origin": "https://example.test/d2.csv"},
            {"id": "d3", "origin": "https://example.test/d3.csv"},
        ],
    }
}
PAYLOADS = {"d1": b"payload-one", "d2": b"payload-two", "d3": b"payload-three"}


class MemoryStorage:
    def __init__(self):
        self.objects = {}

    def put(self, key, content):
        if key in self.objects:
            raise AssertionError(f"overwrite: {key}")
        self.objects[key] = content

    def put_file(self, key, path):
        self.put(key, path.read_bytes())

    def get(self, key):
        return self.objects[key]

    def delete(self, key):
        self.objects.pop(key, None)

    def list_keys(self):
        return set(self.objects)


def make_fetcher(payloads):
    def fetch(dataset, destination):
        destination.write_bytes(payloads[dataset["id"]])

    return fetch


def accept_all(dataset, path):
    return None


def run(storage, run_id, tmp_path, *, fetcher, validator=accept_all, fingerprint=None,
        catalog=CATALOG, source_id="pordata"):
    return collect_datasets(
        catalog,
        source_id,
        storage=storage,
        fetcher=fetcher,
        validator=validator,
        run_id=run_id,
        collected_at_utc="2026-11-11T12:00:00Z",
        work_dir=tmp_path / run_id,
        fingerprint=fingerprint,
    )


def by_id(result):
    return {entry["dataset_id"]: entry for entry in result["datasets"]}


def raw_keys(storage):
    return {key for key in storage.list_keys() if key.startswith("raw/")}


def test_us1_ac1_fr004_fr005_every_dataset_is_stored_with_its_own_manifest_entry(tmp_path):
    storage = MemoryStorage()
    result = run(storage, "run-1", tmp_path, fetcher=make_fetcher(PAYLOADS))
    assert result["status"] == "changed"
    manifest = json.loads(storage.get("manifests/pordata/run-1.json"))
    assert manifest["source_id"] == "pordata"
    assert manifest["run_id"] == "run-1"
    assert manifest["status"] == "changed"
    assert manifest["license_id"] == "not_granted_by_source"
    assert manifest["collected_at_utc"] == "2026-11-11T12:00:00Z"
    entries = {entry["dataset_id"]: entry for entry in manifest["datasets"]}
    assert set(entries) == {"d1", "d2", "d3"}
    for dataset_id, payload in PAYLOADS.items():
        entry = entries[dataset_id]
        assert entry["status"] == "changed"
        assert entry["key"].startswith(f"raw/source=pordata/dataset={dataset_id}/run_id=run-1/")
        assert storage.get(entry["key"]) == payload
        assert entry["sha256"] == hashlib.sha256(payload).hexdigest()
        assert entry["bytes"] == len(payload)


def test_us1_ac2_ac3_fr006_unchanged_is_per_dataset_and_only_the_changed_one_writes_raw(tmp_path):
    storage = MemoryStorage()
    payloads = dict(PAYLOADS)
    first = run(storage, "run-1", tmp_path, fetcher=make_fetcher(payloads))
    raw_after_first = raw_keys(storage)

    second = run(storage, "run-2", tmp_path, fetcher=make_fetcher(payloads))
    assert second["status"] == "unchanged"
    assert {entry["status"] for entry in second["datasets"]} == {"unchanged"}
    assert raw_keys(storage) == raw_after_first
    assert json.loads(storage.get("manifests/pordata/run-2.json"))["status"] == "unchanged"

    payloads["d2"] = b"payload-two-v2"
    third = run(storage, "run-3", tmp_path, fetcher=make_fetcher(payloads))
    entries = by_id(third)
    assert third["status"] == "changed"
    assert entries["d1"]["status"] == "unchanged"
    assert entries["d3"]["status"] == "unchanged"
    assert entries["d2"]["status"] == "changed"
    assert storage.get(entries["d2"]["key"]) == b"payload-two-v2"
    new_keys = raw_keys(storage) - raw_after_first
    assert len(new_keys) == 1 and "dataset=d2/run_id=run-3/" in next(iter(new_keys))
    assert first["status"] == "changed"


def test_us1_ac4_ac5_fr007_fr008_failures_do_not_block_the_others_nor_become_state(tmp_path):
    storage = MemoryStorage()

    def fetch(dataset, destination):
        if dataset["id"] == "d2":
            raise OSError("network interrupted")
        destination.write_bytes(PAYLOADS[dataset["id"]])

    def validate(dataset, path):
        if dataset["id"] == "d3":
            raise ValueError("missing column: Valor")

    first = run(storage, "run-1", tmp_path, fetcher=fetch, validator=validate)
    entries = by_id(first)
    assert first["status"] == "partial"
    assert entries["d1"]["status"] == "changed"
    assert entries["d2"]["status"] == "failed" and "network interrupted" in entries["d2"]["error"]
    assert entries["d3"]["status"] == "failed" and "missing column: Valor" in entries["d3"]["error"]
    assert raw_keys(storage) == {entries["d1"]["key"]}
    manifest = json.loads(storage.get("manifests/pordata/run-1.json"))
    assert manifest["status"] == "partial"
    assert {entry["dataset_id"]: entry["status"] for entry in manifest["datasets"]} == {
        "d1": "changed", "d2": "failed", "d3": "failed",
    }

    second = run(storage, "run-2", tmp_path, fetcher=make_fetcher(PAYLOADS))
    entries = by_id(second)
    assert second["status"] == "changed"
    assert entries["d1"]["status"] == "unchanged"  # o estado de d1 veio do run parcial
    assert entries["d2"]["status"] == "changed" and entries["d3"]["status"] == "changed"


def _ine_document(extracted_at, value="4.29"):
    return [{
        "IndicadorCod": "0014698",
        "DataExtracao": extracted_at,
        "DataUltimoAtualizacao": "2026-09-29",
        "Dados": {"2025": [{"geocod": "1111606", "geodsg": "Ponte da Barca",
                            "ind_string": value.replace(".", ","), "valor": value}]},
        "Sucesso": {"Verdadeiro": [{"Msg": "OK"}]},
    }]


def test_fr006_ine_response_is_unchanged_when_only_the_extraction_time_differs(tmp_path):
    first, second, other = (tmp_path / name for name in ("a.json", "b.json", "c.json"))
    first.write_text(json.dumps(_ine_document("2026-11-11T18:00:00Z")), encoding="utf-8")
    second.write_text(json.dumps(_ine_document("2026-11-11T19:30:00Z")), encoding="utf-8")
    other.write_text(json.dumps(_ine_document("2026-11-11T19:30:00Z", value="5.00")), encoding="utf-8")
    assert fingerprint_ine_response(first) == fingerprint_ine_response(second)
    assert fingerprint_ine_response(first) != fingerprint_ine_response(other)

    catalog = {"ine": {"license_id": "CC-BY-4.0", "collection_method": "api_json",
                       "datasets": [{"id": "rendas", "indicator": "0014698"}]}}
    current = {"doc": _ine_document("2026-11-11T18:00:00Z")}

    def fetch(dataset, destination):
        destination.write_text(json.dumps(current["doc"]), encoding="utf-8")

    def fingerprint(dataset, path):
        return fingerprint_ine_response(path)

    storage = MemoryStorage()
    kwargs = {"fetcher": fetch, "fingerprint": fingerprint, "catalog": catalog, "source_id": "ine"}
    assert run(storage, "run-1", tmp_path, **kwargs)["status"] == "changed"
    raw_after_first = raw_keys(storage)
    current["doc"] = _ine_document("2026-11-11T19:30:00Z")
    assert run(storage, "run-2", tmp_path, **kwargs)["status"] == "unchanged"
    assert raw_keys(storage) == raw_after_first
    current["doc"] = _ine_document("2026-11-11T20:00:00Z", value="5.00")
    assert run(storage, "run-3", tmp_path, **kwargs)["status"] == "changed"


MUNICIPALITIES = {
    "0806": "Lagoa",
    "4201": "Lagoa",
    "3101": "Calheta",
    "4501": "Calheta de São Jorge",
    "4302": "Praia da Vitória",
    "0705": "Évora",
}
SYNONYMS = {
    "Lagoa": "0806",
    "Lagoa [R.A.A.]": "4201",
    "Calheta [R.A.M.]": "3101",
    "Calheta [R.A.A.]": "4501",
    "Vila da Praia da Vitória": "4302",
}


def test_us3_ac2_ac3_fr013_fr014_homonyms_use_explicit_rules_and_unresolved_names_fail(tmp_path):
    names = ["  Évora ", "Lagoa", "Lagoa [R.A.A.]", "Calheta [R.A.M.]", "Vila da Praia da Vitória"]
    resolved = resolve_municipality_names(names, MUNICIPALITIES, SYNONYMS)
    assert resolved == {
        "  Évora ": "0705",
        "Lagoa": "0806",
        "Lagoa [R.A.A.]": "4201",
        "Calheta [R.A.M.]": "3101",
        "Vila da Praia da Vitória": "4302",
    }

    with pytest.raises(UnresolvedMunicipalities) as ambiguous:
        resolve_municipality_names(["Lagoa"], MUNICIPALITIES, {})
    assert ambiguous.value.names == ["Lagoa"]

    with pytest.raises(UnresolvedMunicipalities) as missing:
        resolve_municipality_names(["Évora", "Cidade Inexistente", "Lagoa [X]"], MUNICIPALITIES, SYNONYMS)
    assert missing.value.names == ["Cidade Inexistente", "Lagoa [X]"]
