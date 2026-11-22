"""Assinatura do par e última tentativa (spec 009, FR-015/024/025)."""
import json

import pandas as pd
import pytest

from pipelines.collectors.mobility.catalog import mobility_source
from pipelines.collectors.mobility.municipalities import (
    load_mobility_municipalities,
    routing_group,
)
from pipelines.collectors.mobility.pairs import build_items
from pipelines.collectors.mobility.poles import resolve_poles
from pipelines.collectors.mobility.state import (
    is_current_state,
    latest_attempts,
    pair_signature,
)
from tests.fixtures.mobility.responses import (
    MemoryStorage,
    catalog,
    municipalities,
    raw_poles,
)


def an_item():
    towns = municipalities()
    items = build_items(mobility_source(catalog()), towns, resolve_poles(raw_poles(), towns))
    return next(item for item in items if item["id"] == "0102--aeroporto_x--transit")


@pytest.mark.parametrize("field", ["origin_lat", "origin_lon", "dest_lat", "dest_lon", "mode", "travel_mode",
                                   "routing_preference", "departure_time", "origin"])
def test_the_signature_changes_with_every_field_that_defines_the_pair(field):
    item = an_item()
    changed = {**item, field: "x" if isinstance(item[field], str) or item[field] is None else item[field] + 0.5}
    assert pair_signature(changed) != pair_signature(item)


def test_the_signature_ignores_the_id_and_is_stable():
    item = an_item()
    assert pair_signature(item) == pair_signature({**item, "id": "outro"}) == pair_signature(dict(item))
    assert len(pair_signature(item)) == 64
    assert is_current_state(item, {"pair_signature": pair_signature(item)})
    assert not is_current_state(item, {"pair_signature": "0" * 64})
    assert not is_current_state(item, {})  # a state without a signature is outdated, never silently current


def put_manifest(storage, run_id, at, datasets, source_id="google_distances"):
    storage.put(f"manifests/{source_id}/{run_id}.json", json.dumps({
        "schema_version": 2, "source_id": source_id, "run_id": run_id, "collected_at_utc": at,
        "datasets": datasets}).encode())


def test_latest_attempt_is_the_newest_entry_of_any_status_per_pair():
    storage = MemoryStorage()
    put_manifest(storage, "run-1", "2026-11-21T10:00:00Z",
                 [{"dataset_id": "a", "status": "changed"}, {"dataset_id": "b", "status": "failed", "error": "x"}])
    put_manifest(storage, "run-2", "2026-11-21T11:00:00Z",
                 [{"dataset_id": "a", "status": "failed", "error": "boom"}, {"dataset_id": "c", "status": "pending",
                                                                                  "error": "cota"}])
    put_manifest(storage, "run-0", "2026-11-21T09:00:00Z", [{"dataset_id": "b", "status": "changed"}])
    put_manifest(storage, "other", "2026-11-21T12:00:00Z", [{"dataset_id": "a", "status": "changed"}],
                 source_id="open_meteo")
    attempts = latest_attempts(storage)
    assert {key: (value["status"], value["run_id"]) for key, value in attempts.items()} == {
        "a": ("failed", "run-2"), "b": ("failed", "run-1"), "c": ("pending", "run-2")}


def test_routing_group_maps_regions_and_never_guesses():
    assert routing_group(None) == "continente" and routing_group(float("nan")) == "continente"
    assert routing_group("Região Autónoma da Madeira") == "madeira"
    assert routing_group("Região Autónoma dos Açores") == "acores"
    with pytest.raises(ValueError, match="desconhecida"):
        routing_group("Região Qualquer")


def test_the_loader_reads_the_dimension_and_requires_it(tmp_path):
    with pytest.raises(ValueError, match="Silver"):
        load_mobility_municipalities(tmp_path)
    folder = tmp_path / "dim_municipality"
    folder.mkdir()
    pd.DataFrame({
        "dico": ["0101", "3101"], "official_name": ["Alfa", "Funchalense"], "representative_lat": [38.0, 32.65],
        "representative_lon": [-9.0, -16.9], "district_or_island": ["Distrito A", "Ilha da Madeira"],
        "autonomous_region": [None, "Região Autónoma da Madeira"], "caop_version": ["2025", "2025"],
        "license_id": ["CC-BY-4.0", "CC-BY-4.0"],
    }).to_parquet(folder / "data.parquet")
    towns = load_mobility_municipalities(tmp_path)
    assert [(town["dico"], town["routing_group"], town["autonomous_region"]) for town in towns] == [
        ("0101", "continente", None), ("3101", "madeira", "Região Autónoma da Madeira")]
    assert towns[0]["caop_version"] == "2025" and towns[0]["license_id"] == "CC-BY-4.0"
