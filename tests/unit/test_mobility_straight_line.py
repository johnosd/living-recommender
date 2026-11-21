"""Haversine município–polo (spec 009, FR-005/006)."""
import math

import pytest

from pipelines.collectors.mobility.poles import resolve_poles
from pipelines.collectors.mobility.straight_line import straight_line_rows
from tests.fixtures.mobility.responses import municipalities, raw_poles


def rows_by_key():
    towns = municipalities()
    rows = straight_line_rows(towns, resolve_poles(raw_poles(), towns))
    return rows, {(row["dico"], row["pole_id"]): row for row in rows}


def test_known_distances_and_provenance_fields():
    rows, by = rows_by_key()
    assert by[("0102", "cidade_a")]["km"] == pytest.approx(111.195, abs=0.01)  # one degree of latitude
    assert by[("0201", "cidade_a")]["km"] == pytest.approx(math.hypot(3 * 111.195, 1 * 111.195 * math.cos(math.radians(39.5))),
                                                         rel=0.01)
    assert {row["method"] for row in rows} == {"haversine"} and {row["status"] for row in rows} == {"ok"}
    assert all(row["minutes"] is None and row["error"] is None and row["no_route_reason"] is None for row in rows)


def test_an_airport_at_the_municipality_is_not_an_identity_but_the_municipality_pole_is():
    towns = municipalities()
    raw = raw_poles()
    raw[1]["latitude"], raw[1]["longitude"] = 38.0, -9.0  # airport exactly at municipality 0101
    by = {(row["dico"], row["pole_id"]): row for row in straight_line_rows(towns, resolve_poles(raw, towns))}
    assert by[("0101", "cidade_a")]["km"] == 0.0 and by[("0101", "aeroporto_x")]["km"] == pytest.approx(0.0, abs=1e-9)


def test_every_municipality_gets_every_pole_including_across_islands_and_ordering_is_stable():
    rows, by = rows_by_key()
    assert len(by) == len(rows) == 5 * 4
    assert by[("3102", "cidade_a")]["km"] > 800  # Porto Santo to a mainland pole: straight line ignores eligibility
    assert [(row["dico"], row["pole_id"]) for row in rows] == sorted((row["dico"], row["pole_id"]) for row in rows)
    assert rows == straight_line_rows(list(reversed(municipalities())),
                                      list(reversed(resolve_poles(raw_poles(), municipalities()))))
