"""Cinco contratos públicos da spec 006; sem rede/dbt e sem acesso a estado privado."""

import hashlib
import json

import pandas as pd
import pytest

from pipelines.collectors.censos2021.coverage import assess_censos_coverage
from pipelines.collectors.censos2021.handler import collect_censos
from pipelines.collectors.censos2021.territory import align_censos
from pipelines.collectors.censos2021.transform import read_censos_response
from tests.fixtures.censos2021.responses import (
    catalog,
    dataset,
    downloader,
    metadata,
    response,
    territory_frames,
)
from tests.fixtures.open_meteo.responses import MemoryStorage


def collect(storage, tmp_path, run_id, **options):
    return collect_censos(catalog(), storage=storage, downloader=downloader(**options), run_id=run_id,
                          collected_at_utc="2026-11-13T12:00:00Z", work_dir=tmp_path / run_id)


def test_us1_fr004_fr005_raw_metadata_unchanged_and_revision(tmp_path):
    storage = MemoryStorage()
    first = collect(storage, tmp_path, "one")
    assert first["status"] == "changed"
    manifest = json.loads(storage.get(first["manifest_key"]))
    assert manifest["source_id"] == "censos" and manifest["license_id"] == "CC-BY-4.0"
    assert len(first["datasets"]) == 3
    original = {}
    for entry in first["datasets"]:
        raw = storage.get(entry["key"])
        original[entry["key"]] = raw
        assert entry["sha256"] == hashlib.sha256(raw).hexdigest()
        assert entry["bytes"] == len(raw) and entry["reference_period"] == "2021"
        assert entry["geography_version"] == "2025" and entry["query_signature"]
    old_keys = {k for k in storage.list_keys() if k.startswith("raw/")}
    second = collect(storage, tmp_path, "two", extracted="2026-11-13T13:00:00Z")
    assert second["status"] == "unchanged"
    assert {k for k in storage.list_keys() if k.startswith("raw/")} == old_keys
    third = collect(storage, tmp_path, "three", changed=True)
    assert {e["dataset_id"] for e in third["datasets"] if e["status"] == "changed"} == {"pop_2025_32"}
    assert all(storage.get(key) == content for key, content in original.items())


def test_us1_ac3_fr006_invalid_response_has_no_raw_and_recovers(tmp_path):
    storage = MemoryStorage()
    result = collect(storage, tmp_path, "bad", invalid=True)
    entries = {e["dataset_id"]: e for e in result["datasets"]}
    assert result["status"] == "partial"
    assert entries["pop_2025_32"]["status"] == "failed" and entries["pop_2025_32"]["error"]
    assert not any("dataset=pop_2025_32/" in k for k in storage.list_keys() if k.startswith("raw/"))
    fixed = collect(storage, tmp_path, "fixed")
    assert {e["dataset_id"]: e["status"] for e in fixed["datasets"]} == {
        "meta_2025": "unchanged", "pop_2025_T": "unchanged", "pop_2025_32": "changed"}


def test_fr002_fr012_fr013_reader_preserves_age_bounds_zero_suppression_and_rejects_corruption(tmp_path):
    path = tmp_path / "response.json"
    path.write_bytes(response("32", values={"010103": 0, "0308FC": None}))
    frame = read_censos_response(dataset("32"), path, metadata())
    rows = frame.set_index("source_dicofre")
    assert set(rows.index) == {"010103", "0308FC"}
    assert rows.loc["010103", "value"] == 0 and rows.loc["010103", "value_status"] == "observed"
    assert pd.isna(rows.loc["0308FC", "value"]) and rows.loc["0308FC", "value_status"] == "suppressed"
    assert frame["age_min"].eq(25).all() and frame["age_max"].eq(29).all()
    path.write_bytes(response("92"))
    opened = read_censos_response(dataset("92"), path, metadata())
    assert opened["age_min"].eq(85).all() and opened["age_max"].isna().all()
    for case in ("negative", "duplicate", "wrong_sex", "wrong_period"):
        doc = json.loads(response("32"))
        if case == "negative":
            doc[0]["Dados"]["2021"][0]["valor"] = "-1"
        elif case == "duplicate":
            doc[0]["Dados"]["2021"].append(dict(doc[0]["Dados"]["2021"][0], valor="999"))
        elif case == "wrong_sex":
            doc[0]["Dados"]["2021"][0]["dim_3"] = "1"
        else:
            doc[0]["Dados"] = {"2011": doc[0]["Dados"]["2021"]}
        path.write_text(json.dumps(doc), encoding="utf-8")
        with pytest.raises(ValueError):
            read_censos_response(dataset("32"), path, metadata())


def test_fr008_fr009_fr010_fr011_official_precedence_inheritance_and_partial_absence():
    observations, parishes, crosswalk, categories = territory_frames()
    result = align_censos(observations, parishes, crosswalk, categories=categories, target_version="2025")
    assert len(result) == 8 and not result.duplicated(["dicofre", "age_code"]).any()
    total = result[result["age_code"] == "T"].set_index("dicofre")
    assert (total.loc["0308FC", "value"], total.loc["0308FC", "coverage_status"]) == (11, "own")
    assert (total.loc["0308FD", "value"], total.loc["0308FD", "coverage_status"]) == (300, "inherited")
    assert total.loc["0308FD", "source_dicofre"] == "030880"
    assert total.loc["021123", "coverage_status"] == "missing" and pd.isna(total.loc["021123", "value"])
    assert total.loc["021123", "reason"] == "territorial_ambiguity"
    assert set(result["dico"]) == set(parishes["dico"])
    with pytest.raises(ValueError):
        align_censos(observations, parishes, crosswalk, categories=categories, target_version="2026")


def test_fr014_fr015_sc001_sc006_coverage_distinguishes_documented_absence_from_lost_record():
    _, parishes, _, categories = territory_frames()
    prepared = pd.DataFrame([
        {"dicofre": code, "age_code": age, "coverage_status": "missing" if code == "021123" else
         "inherited" if code == "0308FD" else "own", "value": None if code == "021123" else 100,
         "reason": "territorial_ambiguity" if code == "021123" else None}
        for code in parishes["dicofre"] for age in categories["age_code"]
    ])
    good = assess_censos_coverage(prepared, parishes, categories)
    assert good["ready"] is True and good["blockers"] == []
    assert good["expected_observations"] == 8 and good["counts"] == {"own": 4, "inherited": 2, "missing": 2}
    lost = assess_censos_coverage(prepared.iloc[:-1], parishes, categories)
    assert lost["ready"] is False and "missing_record" in lost["blockers"]
    failed_input = assess_censos_coverage(prepared, parishes, categories, input_errors=["collect_failed"])
    assert failed_input["ready"] is False and "collect_failed" in failed_input["blockers"]
    unexplained = prepared.copy()
    unexplained.loc[unexplained["coverage_status"] == "missing", "reason"] = None
    unknown = assess_censos_coverage(unexplained, parishes, categories)
    assert unknown["ready"] is False and "unexplained_absence" in unknown["blockers"]
