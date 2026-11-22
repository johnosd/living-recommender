"""Estados das linhas por par (spec 009, logic/pares-e-estados.md §5)."""
from copy import deepcopy

import pytest

from pipelines.collectors._shared.dataset_manifest import (
    encode_dataset_manifest,
    make_dataset_manifest,
)
from pipelines.collectors.mobility.catalog import mobility_source
from pipelines.collectors.mobility.pairs import build_items
from pipelines.collectors.mobility.poles import resolve_poles
from pipelines.collectors.mobility.rows import build_distance_rows
from pipelines.collectors.mobility.state import pair_signature
from tests.fixtures.mobility.responses import (
    MemoryStorage,
    catalog,
    municipalities,
    raw_poles,
)

SOURCE = mobility_source(catalog())


def setup():
    towns = municipalities()
    poles = resolve_poles(raw_poles(), towns)
    return towns, poles, {item["id"]: item for item in build_items(SOURCE, towns, poles)}


def changed(item, **extra):
    return {"dataset_id": item["id"], "status": "changed", "key": f"raw/source=google_distances/x/{item['id']}.json",
            "sha256": "a" * 64, "bytes": 10, "fingerprint": "f", "route_status": "ROUTE_EXISTS",
            "distance_m": 12000, "duration_s": 900, "pair_signature": pair_signature(item), **extra}


def failed(item, error="boom"):
    return {"dataset_id": item["id"], "status": "failed", "error": error}


def pending(item):
    return {"dataset_id": item["id"], "status": "pending", "error": "cota"}


def put(storage, run_id, at, entries):
    manifest = make_dataset_manifest(SOURCE, source_id="google_distances", run_id=run_id, collected_at_utc=at,
                                     datasets=entries)
    storage.put(f"manifests/google_distances/{run_id}.json", encode_dataset_manifest(manifest))


def by_key(storage, poles=None, **kwargs):
    towns, resolved, _ = setup()
    rows = build_distance_rows(kwargs.get("catalog", catalog()), municipalities=towns, poles=poles or resolved,
                               storage=storage, processed_at_utc="2026-11-21T13:00:00Z")
    return rows, {(row["dico"], row["pole_id"], row["mode"]): row for row in rows}


def test_each_state_becomes_one_status_and_never_a_value_that_does_not_exist():
    _, _, items = setup()
    storage = MemoryStorage()
    put(storage, "run-1", "2026-11-21T10:00:00Z", [
        changed(items["0101--aeroporto_x--driving"]),
        changed(items["0102--aeroporto_x--driving"], route_status="ROUTE_NOT_FOUND", distance_m=None, duration_s=None),
        failed(items["0201--aeroporto_x--driving"], "HTTP 500"),
        pending(items["0201--cidade_a--driving"]),
    ])
    _, by = by_key(storage)
    ok = by[("0101", "aeroporto_x", "driving")]
    assert (ok["status"], ok["km"], ok["minutes"], ok["source_run_id"]) == ("ok", 12.0, 15.0, "run-1")
    assert ok["calculated_at_utc"] == "2026-11-21T10:00:00Z" and not ok["stale"] and ok["method"] == "google_routes_v2"
    no_route = by[("0102", "aeroporto_x", "driving")]
    assert (no_route["status"], no_route["no_route_reason"], no_route["km"], no_route["minutes"]) == (
        "sem_rota", "ROUTE_NOT_FOUND", None, None)
    fail = by[("0201", "aeroporto_x", "driving")]
    assert (fail["status"], fail["error"], fail["km"]) == ("falha", "HTTP 500", None)
    assert by[("0201", "cidade_a", "driving")]["status"] == "pendente"  # a pending entry is not a failure
    assert by[("0102", "cidade_a", "transit")]["status"] == "pendente"  # never queried at all


def test_identity_rows_are_zero_ok_without_a_call_or_a_run():
    _, by = by_key(MemoryStorage())
    row = by[("0101", "cidade_a", "driving")]
    assert (row["status"], row["km"], row["minutes"], row["method"], row["source_run_id"]) == (
        "ok", 0.0, 0.0, "identity", None)


def test_a_newer_failure_does_not_erase_a_valid_state_and_a_newer_success_replaces_an_older_failure():
    _, _, items = setup()
    item = items["0101--aeroporto_x--driving"]
    storage = MemoryStorage()
    put(storage, "run-1", "2026-11-21T10:00:00Z", [changed(item)])
    put(storage, "run-2", "2026-11-21T11:00:00Z", [failed(item)])
    assert by_key(storage)[1][("0101", "aeroporto_x", "driving")]["status"] == "ok"
    storage = MemoryStorage()
    put(storage, "run-1", "2026-11-21T10:00:00Z", [failed(item)])
    put(storage, "run-2", "2026-11-21T11:00:00Z", [changed(item, distance_m=5000, duration_s=300)])
    row = by_key(storage)[1][("0101", "aeroporto_x", "driving")]
    assert (row["status"], row["km"], row["minutes"]) == ("ok", 5.0, 5.0)


def test_a_changed_pole_marks_only_its_pairs_stale_and_keeps_their_values():
    _, _, items = setup()
    storage = MemoryStorage()
    put(storage, "run-1", "2026-11-21T10:00:00Z", [changed(items[key]) for key in items if key.endswith("driving")])
    moved = deepcopy(raw_poles())
    moved[1]["latitude"] = 38.79
    _, by = by_key(storage, resolve_poles(moved, municipalities()))
    stale = {key for key, row in by.items() if row["stale"]}
    assert stale == {(dico, "aeroporto_x", "driving") for dico in ("0101", "0102", "0201")}
    assert all(by[key]["status"] == "ok" and by[key]["km"] == 12.0 for key in stale)


def test_only_the_enabled_modes_get_route_rows_and_provenance_is_complete():
    source = deepcopy(catalog())
    del source["sources"]["google_distances"]["modes"]["transit"]
    rows, by = by_key(MemoryStorage(), catalog=source)
    assert {row["mode"] for row in rows} == {"straight_line", "driving"}
    assert len(rows) == 5 * 4 + 8
    line, route = by[("0102", "cidade_a", "straight_line")], by[("0102", "cidade_a", "driving")]
    assert route["attribution"] == "Tempos de viagem: Google" and route["license_id"] == "not_granted_by_source"
    assert line["attribution"] is None and line["license_id"] is None  # the fixture dimension has no license column
    assert len({row["poles_catalog_version"] for row in rows}) == 1
    assert {row["processed_at_utc"] for row in rows} == {"2026-11-21T13:00:00Z"}
    assert {row["reference_period"] for row in rows} == {"2026-12"}


@pytest.mark.parametrize("field", ["dico", "pole_id", "mode", "status", "stale"])
def test_every_row_has_the_columns_the_staging_expects(field):
    rows, _ = by_key(MemoryStorage())
    assert all(field in row for row in rows)


def test_every_row_names_its_source():
    rows, _ = by_key(MemoryStorage())
    assert {row["source_id"] for row in rows if row["mode"] == "straight_line"} == {"caop"}
    assert {row["source_id"] for row in rows if row["mode"] != "straight_line"} == {"google_distances"}
