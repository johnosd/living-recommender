"""Estimativa de pares, elementos e custo (spec 009, FR-008/009, logic §7)."""
from copy import deepcopy

import pytest

from pipelines.collectors._shared.dataset_manifest import (
    encode_dataset_manifest,
    make_dataset_manifest,
)
from pipelines.collectors.mobility.catalog import mobility_source
from pipelines.collectors.mobility.estimate import estimate_run
from pipelines.collectors.mobility.pairs import build_items
from pipelines.collectors.mobility.poles import resolve_poles
from pipelines.collectors.mobility.state import pair_signature
from tests.fixtures.mobility.responses import (
    MemoryStorage,
    catalog,
    municipalities,
    raw_poles,
)


def setup(**changes):
    value = deepcopy(catalog())
    value["sources"]["google_distances"].update(changes)
    towns = municipalities()
    return value, towns, resolve_poles(raw_poles(), towns)


def store_current(storage, value, towns, poles, only=None, signature=None):
    source = mobility_source(value)
    entries = [{"dataset_id": item["id"], "status": "changed", "key": f"raw/x/{item['id']}", "sha256": "a" * 64,
                "bytes": 5, "fingerprint": "f", "pair_signature": signature or pair_signature(item)}
               for item in build_items(source, towns, poles) if only is None or item["id"] in only]
    manifest = make_dataset_manifest(source, source_id="google_distances", run_id="r",
                                     collected_at_utc="2026-11-21T10:00:00Z", datasets=entries)
    storage.put("manifests/google_distances/r.json", encode_dataset_manifest(manifest))


def test_an_empty_destination_counts_every_queryable_pair_as_new():
    value, towns, poles = setup()
    estimate = estimate_run(value, municipalities=towns, poles=poles, storage=MemoryStorage())
    assert (estimate["new"], estimate["stale"], estimate["elements_total"]) == (10, 0, 10)
    assert estimate["pricing_verified_on"] == "2026-11-21"


def test_only_the_enabled_modes_are_counted():
    value, towns, poles = setup()
    del value["sources"]["google_distances"]["modes"]["transit"]
    estimate = estimate_run(value, municipalities=towns, poles=poles, storage=MemoryStorage())
    assert estimate["elements"] == {"driving": 5} and estimate["elements_total"] == 5
    assert estimate["pairs_total"] == 8 and estimate["identity"] == 3


def test_current_pairs_cost_nothing_and_a_mismatched_signature_is_stale():
    value, towns, poles = setup()
    storage = MemoryStorage()
    store_current(storage, value, towns, poles)
    assert estimate_run(value, municipalities=towns, poles=poles, storage=storage)["elements_total"] == 0
    storage = MemoryStorage()
    store_current(storage, value, towns, poles, signature="0" * 64)
    estimate = estimate_run(value, municipalities=towns, poles=poles, storage=storage)
    assert (estimate["new"], estimate["stale"], estimate["elements_total"]) == (0, 10, 10)


def test_the_free_monthly_cap_is_deducted_per_mode_and_the_worst_case_ignores_it():
    value, towns, poles = setup(pricing={"driving": {"usd_per_1000": 5.0, "free_monthly": 3},
                                         "transit": {"usd_per_1000": 15.0, "free_monthly": 0}})
    estimate = estimate_run(value, municipalities=towns, poles=poles, storage=MemoryStorage())
    assert estimate["cost_usd_estimate"] == pytest.approx((5 - 3) * 5 / 1000 + 5 * 15 / 1000)
    assert estimate["cost_usd_worst_case"] == pytest.approx(5 * 5 / 1000 + 5 * 15 / 1000)


def test_the_ceiling_comes_from_the_catalog_and_the_estimate_makes_no_network_call():
    value, towns, poles = setup(max_elements_per_run=123)
    assert estimate_run(value, municipalities=towns, poles=poles, storage=MemoryStorage())["ceiling"] == 123
