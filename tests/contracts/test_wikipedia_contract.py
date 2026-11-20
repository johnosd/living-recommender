"""Cinco contratos da spec 008; fronteiras públicas e colaboradores sem rede."""

import hashlib
import json
from copy import deepcopy

from pipelines.collectors.wikipedia.coverage import assess_wikipedia_coverage
from pipelines.collectors.wikipedia.extract import extract_article
from pipelines.collectors.wikipedia.handler import collect_wikipedia
from tests.fixtures.open_meteo.responses import MemoryStorage
from tests.fixtures.wikipedia.responses import (
    associations,
    catalog,
    documents,
    fetcher,
    municipalities,
)

TERRITORY_HASH = hashlib.sha256(b"fixture-caop-2025").hexdigest()


def collect(storage, tmp_path, run_id, fetch, *, mapping=None, source_catalog=None):
    return collect_wikipedia(
        source_catalog if source_catalog is not None else catalog(), municipalities=municipalities(),
        associations=mapping if mapping is not None else associations(),
        territory_hash=TERRITORY_HASH, storage=storage, fetcher=fetch,
        run_id=run_id, collected_at_utc="2026-11-20T10:00:00Z", work_dir=tmp_path / run_id,
    )


def raw_snapshot(storage):
    return {key: storage.get(key) for key in storage.list_keys() if key.startswith("raw/")}


def entries(result):
    return {entry["dico"]: entry for entry in result["entries"]}


def test_us1_fr004_fr008_fr009_pinned_identity_and_immutable_raw(tmp_path):
    storage = MemoryStorage()
    fetch, calls = fetcher()
    result = collect(storage, tmp_path, "first", fetch)
    assert result["status"] == "changed" and len(calls) == 2
    manifest = json.loads(storage.get(result["manifest_key"]))
    assert manifest["source_id"] == "wikipedia" and manifest["language"] == "pt"
    assert manifest["license_id"] == "CC-BY-SA-4.0"
    assert manifest["territory_hash"] == TERRITORY_HASH
    assert manifest["associations_snapshot"] == associations()
    for code, entry in entries(result).items():
        assert entry["status"] == "changed" and entry["revision_id"] == 1001
        assert entry["page_id"] == (101 if code == "0001" else 102)
        assert entry["scope"] == "municipality" and entry["association_hash"]
        assert "oldid=1001" in entry["permanent_url"]
        assert {f["role"] for f in entry["files"]} == {"metadata", "content"}
        for file in entry["files"]:
            payload = storage.get(file["key"])
            assert file["sha256"] == hashlib.sha256(payload).hexdigest()
            assert file["bytes"] == len(payload)
    assert len(raw_snapshot(storage)) == 4


def test_us1_ac2_ac4_fr006_fr009_invalid_identity_revision_and_api_error_do_not_become_state(tmp_path):
    # Constitution III/IV: homônimo, desambiguação, revisão incoerente e erro HTTP200.
    for case in ("wrong_page", "disambiguation", "wrong_revision", "api_error"):
        storage = MemoryStorage()
        meta, parsed = documents()
        if case == "wrong_page":
            meta["query"]["pages"][0].update(pageid=999, title="Corvo")
            meta["query"]["pages"][0]["pageprops"] = {"wikibase_item": "Q43365"}
        elif case == "disambiguation":
            meta["query"]["pages"][0]["pageprops"]["disambiguation"] = ""
        elif case == "wrong_revision":
            parsed["parse"]["revid"] = 9999
        else:
            parsed = {"error": {"code": "badrevids", "info": "revision unavailable"}}
        bad, _ = fetcher(overrides={"0001": (meta, parsed)})
        result = collect(storage, tmp_path, f"bad-{case}", bad)
        assert result["status"] == "partial"
        assert entries(result)["0001"]["status"] == "failed"
        assert entries(result)["0001"]["error"]
        assert entries(result)["0002"]["status"] == "changed"
        assert not any("dico=0001/" in k for k in raw_snapshot(storage))
        old_raw = raw_snapshot(storage)
        good, _ = fetcher()
        recovered = collect(storage, tmp_path, f"fixed-{case}", good)
        assert entries(recovered)["0001"]["status"] == "changed"
        assert entries(recovered)["0002"]["status"] == "unchanged"
        assert all(storage.get(k) == v for k, v in old_raw.items())


def test_us3_fr019_fr020_fr021_catalog_and_mapping_are_frozen_and_rechecked(tmp_path):
    storage = MemoryStorage()
    mapping = associations()
    source_catalog = catalog()

    def mutate_caller(association):
        if association["dico"] == "0001":
            mapping[1]["page_id"] = 999
            source_catalog["sources"]["wikipedia"]["language"] = "en"

    initial_fetch, calls = fetcher(on_fetch=mutate_caller)
    first = collect(storage, tmp_path, "one", initial_fetch, mapping=mapping,
                    source_catalog=source_catalog)
    assert [a["page_id"] for a in calls] == [101, 102]
    assert json.loads(storage.get(first["manifest_key"]))["associations_snapshot"] == associations()
    assert json.loads(storage.get(first["manifest_key"]))["catalog_snapshot"]["language"] == "pt"
    original = raw_snapshot(storage)
    repeat_fetch, repeat_calls = fetcher()
    repeated = collect(storage, tmp_path, "two", repeat_fetch)
    assert len(repeat_calls) == 2  # verificar fonte; não confundir cache eterno com unchanged
    assert repeated["status"] == "unchanged" and raw_snapshot(storage) == original
    new_meta, new_parsed = documents(revision=1002)
    changed_fetch, _ = fetcher(overrides={"0001": (new_meta, new_parsed)})
    changed = collect(storage, tmp_path, "three", changed_fetch)
    assert entries(changed)["0001"]["status"] == "changed"
    assert entries(changed)["0001"]["revision_id"] == 1002
    assert entries(changed)["0002"]["status"] == "unchanged"
    assert all(storage.get(k) == v for k, v in original.items())
    revised_mapping = associations()
    revised_mapping[0]["evidence_note"] += " Evidência de abrangência revalidada."
    again, _ = fetcher(overrides={"0001": (new_meta, new_parsed)})
    revalidated = collect(storage, tmp_path, "four", again, mapping=revised_mapping)
    assert entries(revalidated)["0001"]["association_hash"] != entries(changed)["0001"]["association_hash"]
    assert all(storage.get(k) == v for k, v in original.items())


def test_us2_fr010_fr011_fr012_fr013_complete_sections_keep_boundaries_and_nested_context():
    metadata, parsed = documents()
    originals = deepcopy((metadata, parsed))
    result = extract_article(metadata, parsed)
    assert (metadata, parsed) == originals
    assert result["introduction"] == "Alfa é um município português. Conheça Portugal."
    sections = {s["title"]: s["section_id"] for s in result["sections"]}
    assert {"População", "Religiões", "Saúde", "Referências"} <= set(sections)
    blocks = result["blocks"]
    assert len({b["block_id"] for b in blocks}) == len(blocks)
    population = [b for b in blocks if b["section_id"] == sections["População"]]
    assert not any("religião" in (b.get("text") or "") for b in population)
    assert any(b.get("text") == "Censos locais" for b in population)
    assert any(b.get("text") == "Freguesia Beta" and b.get("parent_block_id") for b in population)
    health = [b.get("text") for b in blocks if b["section_id"] == sections["Saúde"]]
    assert "Primeiro parágrafo de saúde." in health and "Segundo parágrafo de saúde." in health
    assert "Hospital Alfa" in health and "Centro Beta" in health
    for text in ["Alfa é um município português.", "Parágrafo de religião.",
                 "Segundo parágrafo de saúde.", "Freguesia Beta"]:
        assert result["full_text"].count(text) == 1
    links = [link for block in blocks for link in block.get("links", [])]
    assert any(link["href"] == "#cite_note-1" for link in links)
    assert any(link["href"] == "https://example.test/fonte" for link in links)
    assert result["wikidata_id"] == "Q101"
    assert result["english_url"] == "https://en.wikipedia.org/wiki/Alfa"


def test_us4_fr025_fr026_fr027_fr028_readiness_rejects_loss_and_latest_failure():
    valid = {"dico": "0001", "status": "valid", "identity_validated": True,
             "revision_id": 1001, "extraction_complete": True, "reason": None}
    absent = {"dico": "0002", "status": "absent", "reason": "no_appropriate_pt_article",
              "absence_evidence": {"reviewer": "fixture", "reviewed_at_utc": "2026-11-20T10:00:00Z",
                                   "evidence_note": "Busca e títulos candidatos revisados sem artigo municipal.",
                                   "evidence_url": "https://pt.wikipedia.org/wiki/Especial:Pesquisar"}}
    good = assess_wikipedia_coverage(municipalities(), [valid, absent])
    assert good["ready"] is True and good["blockers"] == []
    assert good["expected_municipalities"] == 2
    assert good["counts"] == {"valid": 1, "absent": 1}
    failed = dict(valid, status="failed", error="network", previous_valid_revision_id=1001)
    unexplained = dict(absent, absence_evidence=None)
    cases = [[valid], [valid, absent, deepcopy(valid)], [valid, unexplained], [failed, absent],
             [dict(valid, identity_validated=False), absent],
             [dict(valid, extraction_complete=False), absent]]
    for rows in cases:
        report = assess_wikipedia_coverage(municipalities(), rows)
        assert report["ready"] is False and report["blockers"]
    assert assess_wikipedia_coverage(municipalities(), [valid, absent], input_errors=("checksum",))["ready"] is False
