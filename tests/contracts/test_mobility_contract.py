"""Locked contracts for the mobility ingestion (spec 009).

Only public boundaries are exercised: `resolve_poles`, `route_pairs`, `straight_line_rows`, `estimate_run`,
`make_routes_fetcher` (over an injected `httpx` mock transport), `collect_mobility`, `build_distance_rows` and
the `collect_mobility` CLI `main`, with injected storage/fetcher/environment and no network.
"""

import json
from collections import Counter

import httpx
import pytest

from pipelines.cli import collect_mobility as cli
from pipelines.collectors._shared.datasets import QuotaExhausted
from pipelines.collectors._shared.http import USER_AGENT
from pipelines.collectors.mobility.estimate import estimate_run
from pipelines.collectors.mobility.fetch import make_routes_fetcher
from pipelines.collectors.mobility.handler import collect_mobility
from pipelines.collectors.mobility.pairs import route_pairs
from pipelines.collectors.mobility.poles import resolve_poles
from pipelines.collectors.mobility.rows import build_distance_rows
from pipelines.collectors.mobility.straight_line import straight_line_rows
from tests.fixtures.mobility.responses import (
    COLLECTED_AT,
    KEY_SENTINEL,
    PROCESSED_AT,
    TRANSIT_DEPARTURE,
    MemoryStorage,
    api_error,
    catalog,
    municipalities,
    raw_poles,
    routes_element_error,
    routes_not_found,
    routes_ok,
    write_catalog,
)

SOURCE = catalog()["sources"]["google_distances"]
MODES = ("driving", "transit")
TRAVEL_MODE = {"DRIVE": "driving", "TRANSIT": "transit"}


def setup():
    towns = municipalities()
    return towns, resolve_poles(raw_poles(), towns)


def raw_keys(storage):
    return sorted(key for key in storage.list_keys() if key.startswith("raw/"))


def run(storage, run_id, tmp_path, fetcher, *, max_elements=None):
    towns, poles = setup()
    return collect_mobility(catalog(), municipalities=towns, poles=poles, storage=storage, fetcher=fetcher,
                            run_id=run_id, collected_at_utc=COLLECTED_AT, work_dir=tmp_path / run_id,
                            max_elements=max_elements)


def rows_by_key(storage, poles=None):
    towns, resolved = setup()
    rows = build_distance_rows(catalog(), municipalities=towns, poles=poles or resolved, storage=storage,
                               processed_at_utc=PROCESSED_AT)
    return rows, {(row["dico"], row["pole_id"], row["mode"]): row for row in rows}


def reply(status, body):
    return httpx.Response(status, content=body.encode("utf-8"), headers={"content-type": "application/json"})


def ids_of(entries, status):
    return sorted(entry["dataset_id"] for entry in entries if entry["status"] == status)


def test_us1_fr001_fr004_fr005_fr006_fr013_fr014_eligible_pairs_and_straight_line_cover_every_municipality():
    towns, poles = setup()
    rows = straight_line_rows(towns, poles)
    assert len(rows) == 5 * 4 == len({(row["dico"], row["pole_id"]) for row in rows})
    assert all(row["mode"] == "straight_line" and row["status"] == "ok" and row["km"] >= 0 for row in rows)
    by = {(row["dico"], row["pole_id"]): row for row in rows}
    assert by[("0101", "cidade_a")]["km"] == 0.0 and by[("3101", "funchal")]["km"] == 0.0
    assert by[("0102", "cidade_a")]["km"] == pytest.approx(111.195, abs=0.5)  # 1 degree of latitude
    assert by[("3101", "aeroporto_x")]["km"] > 900  # the islands also have a straight line to the mainland poles

    pairs = route_pairs(towns, poles)
    assert len(pairs) == 16
    expected = {("0101", "cidade_a"): True, ("0102", "cidade_a"): False, ("0201", "cidade_a"): False,
                ("0101", "aeroporto_x"): False, ("0102", "aeroporto_x"): False, ("0201", "aeroporto_x"): False,
                ("0201", "sede_b"): True, ("3101", "funchal"): True}
    assert {(p["dico"], p["pole_id"], p["mode"]): p["identity"] for p in pairs} == {
        (dico, pole, mode): identity for (dico, pole), identity in expected.items() for mode in MODES}
    # no route pair crosses a routing group, a district seat or an island: Porto Santo has none, "0101" has no seat
    assert not any(p["dico"] == "3102" or (p["dico"] == "0101" and p["pole_id"] == "sede_b") for p in pairs)


def test_us2_ac1_ac2_ac3_fr008_fr009_fr010_estimate_needs_no_key_or_network_and_spending_needs_confirmation(
        tmp_path, capsys):
    towns, poles = setup()
    estimate = estimate_run(catalog(), municipalities=towns, poles=poles, storage=MemoryStorage())
    assert estimate["pairs_total"] == 16 and estimate["identity"] == 6
    assert estimate["elements"] == {"driving": 5, "transit": 5} and estimate["elements_total"] == 10
    assert estimate["new"] == 10 and estimate["stale"] == 0 and estimate["ceiling"] == 8
    assert estimate["cost_usd_estimate"] == 0.0  # inside the free monthly caps
    assert estimate["cost_usd_worst_case"] == pytest.approx(5 * 5 / 1000 + 5 * 15 / 1000)

    catalog_path = tmp_path / "sources.yml"
    write_catalog(catalog_path)
    calls, fetched = [], []

    def transport(request):
        calls.append(request.url)
        return httpx.Response(500)

    def run_cli(*flags, env=None, fake=False):
        storage = MemoryStorage()

        def fetcher(item, destination):
            fetched.append(item["id"])
            destination.write_text(routes_ok(), encoding="utf-8")

        try:
            code = cli.main(["--local", "--root", str(tmp_path), "--catalog", str(catalog_path), *flags],
                            client=httpx.Client(transport=httpx.MockTransport(transport)),
                            fetcher=fetcher if fake else None, storage=storage,
                            env={} if env is None else env, municipalities=towns, poles=poles,
                            sleep=lambda seconds: None)
        except SystemExit as exit_:
            code = exit_.code
        return code, storage

    key = {"GOOGLE_ROUTES_API_KEY": KEY_SENTINEL}
    code, storage = run_cli()  # default mode: estimate only, no key
    assert code == 0 and not calls and not raw_keys(storage)
    assert "10" in capsys.readouterr().out

    code, _ = run_cli("--execute", "--confirm-elements", "10")  # no key: refuse before any call
    err = capsys.readouterr().err
    assert code not in (0, None) and "GOOGLE_ROUTES_API_KEY" in err and not calls and KEY_SENTINEL not in err

    for flags in (("--execute", "--confirm-elements", "10"),  # estimate 10 above the ceiling of 8
                  ("--execute", "--max-elements", "10"),  # no confirmation of the estimate
                  ("--execute", "--confirm-elements", "9", "--max-elements", "10")):  # wrong confirmation
        code, storage = run_cli(*flags, env=key)
        assert code not in (0, None) and not calls and not fetched and not raw_keys(storage)

    code, storage = run_cli("--execute", "--confirm-elements", "10", "--max-elements", "10",
                            env=key, fake=True)
    assert code == 0 and len(fetched) == 10 and len(raw_keys(storage)) == 10


def test_us2_ac4_ac6_ac7_fr011_fr012_fr016_fr017_fr018_responses_become_ok_sem_rota_falha_or_pendente(tmp_path):
    towns, _ = setup()
    dico_by_lat = {town["latitude"]: town["dico"] for town in towns}
    pole_by_lat = {38.0: "cidade_a", 38.78: "aeroporto_x", 41.0: "sede_b", 32.65: "funchal"}
    scenario = {
        ("0101", "aeroporto_x", "driving"): reply(200, routes_ok(12000, 900)),
        ("0101", "aeroporto_x", "transit"): reply(200, routes_not_found()),
        ("0102", "aeroporto_x", "driving"): reply(200, routes_element_error()),
        ("0102", "aeroporto_x", "transit"): reply(200, routes_ok(30000, 3600)),
        ("0102", "cidade_a", "driving"): reply(403, api_error("PERMISSION_DENIED", "denied", 403)),
    }
    seen = []

    def transport(request):
        body = json.loads(request.content)
        origin = body["origins"][0]["waypoint"]["location"]["latLng"]["latitude"]
        destination = body["destinations"][0]["waypoint"]["location"]["latLng"]["latitude"]
        key = (dico_by_lat[origin], pole_by_lat[destination], TRAVEL_MODE[body["travelMode"]])
        seen.append((key, request.headers, body))
        return scenario[key]

    fetch = make_routes_fetcher(SOURCE, api_key=KEY_SENTINEL, sleep=lambda seconds: None,
                                client=httpx.Client(transport=httpx.MockTransport(transport)))
    storage = MemoryStorage()
    result = run(storage, "run-1", tmp_path, fetch)

    assert result["status"] == "partial" and result["quota_exhausted"] is False
    assert ids_of(result["datasets"], "changed") == ["0101--aeroporto_x--driving", "0101--aeroporto_x--transit",
                                                     "0102--aeroporto_x--transit"]
    assert ids_of(result["datasets"], "failed") == ["0102--aeroporto_x--driving"]
    assert len(ids_of(result["datasets"], "pending")) == 6  # the denied key stops the run: it and the rest wait
    assert [key for key, _, _ in seen] == list(scenario)  # nothing was called after the authorization error
    for key, headers, body in seen:
        assert headers["x-goog-api-key"] == KEY_SENTINEL and headers["user-agent"] == USER_AGENT
        assert headers["x-goog-fieldmask"]
        if key[2] == "transit":
            assert body["departureTime"] == TRANSIT_DEPARTURE
        else:
            assert body["routingPreference"] == "TRAFFIC_UNAWARE" and "departureTime" not in body
    raw = raw_keys(storage)
    assert len(raw) == 3  # ok and sem_rota are valid answers; the element error is not stored
    ok_key = next(key for key in raw if "dataset=0101--aeroporto_x--driving/" in key)
    assert storage.get(ok_key) == routes_ok(12000, 900).encode()

    rows, by = rows_by_key(storage)
    assert len(rows) == 5 * 4 + 16
    ok = by[("0101", "aeroporto_x", "driving")]
    assert (ok["status"], ok["km"], ok["minutes"], ok["no_route_reason"]) == ("ok", pytest.approx(12.0),
                                                                            pytest.approx(15.0), None)
    assert by[("0102", "aeroporto_x", "transit")]["km"] == pytest.approx(30.0)
    assert by[("0102", "aeroporto_x", "transit")]["minutes"] == pytest.approx(60.0)
    no_route = by[("0101", "aeroporto_x", "transit")]
    assert (no_route["status"], no_route["no_route_reason"]) == ("sem_rota", "ROUTE_NOT_FOUND")
    assert by[("0102", "aeroporto_x", "driving")]["status"] == "falha"
    assert by[("0102", "cidade_a", "driving")]["status"] == "pendente"
    identity = by[("0101", "cidade_a", "driving")]
    assert (identity["status"], identity["km"], identity["minutes"]) == ("ok", 0.0, 0.0)
    for row in rows:  # constitution III: a value is never invented
        if row["mode"] != "straight_line" and row["status"] != "ok":
            assert row["km"] is None and row["minutes"] is None
    assert Counter(row["status"] for row in rows if row["mode"] == "driving") == {"ok": 4, "falha": 1, "pendente": 3}
    assert Counter(row["status"] for row in rows if row["mode"] == "transit") == {"ok": 4, "sem_rota": 1,
                                                                                  "pendente": 3}
    assert Counter(row["status"] for row in rows if row["mode"] == "straight_line") == {"ok": 20}


def test_us2_ac5_us3_ac1_ac3_fr015_fr024_fr025_resume_skips_stored_pairs_and_a_changed_pole_stales_only_its_pairs(
        tmp_path):
    storage, calls = MemoryStorage(), []

    def fetch(item, destination):
        calls.append(item["id"])
        destination.write_text(routes_ok(), encoding="utf-8")

    def interrupted(item, destination):
        if len(calls) == 4:
            raise QuotaExhausted("fixture: daily quota")
        fetch(item, destination)

    first = run(storage, "run-1", tmp_path, interrupted)
    assert first["quota_exhausted"] is True and len(first["datasets"]) == 10
    done = list(calls)
    assert len(done) == 4 and len(ids_of(first["datasets"], "pending")) == 6

    calls.clear()
    second = run(storage, "run-2", tmp_path, fetch)
    assert len(calls) == 6 and not set(calls) & set(done) and second["status"] == "changed"
    calls.clear()
    third = run(storage, "run-3", tmp_path, fetch)
    assert third["up_to_date"] is True and not calls  # nothing is queried or charged again

    rows, _ = rows_by_key(storage)
    assert not [row for row in rows if row["status"] == "pendente"]
    for mode in (*MODES, "straight_line"):
        assert sum(row["mode"] == mode for row in rows) == (8 if mode != "straight_line" else 20)
    assert not any(row["stale"] for row in rows)
    before = raw_keys(storage)
    assert len(before) == 10

    moved = raw_poles()
    moved[1]["latitude"] = 38.79  # the airport moved: only its six pairs are outdated
    towns = municipalities()
    new_poles = resolve_poles(moved, towns)
    rows, by = rows_by_key(storage, new_poles)
    assert {key for key, row in by.items() if row["stale"]} == {
        (dico, "aeroporto_x", mode) for dico in ("0101", "0102", "0201") for mode in MODES}
    assert all(row["status"] == "ok" and row["km"] is not None for row in by.values() if row["stale"])
    estimate = estimate_run(catalog(), municipalities=towns, poles=new_poles, storage=storage)
    assert estimate["stale"] == 6 and estimate["new"] == 0 and estimate["elements_total"] == 6

    calls.clear()
    collect_mobility(catalog(), municipalities=towns, poles=new_poles, storage=storage, fetcher=fetch,
                     run_id="run-4", collected_at_utc=COLLECTED_AT, work_dir=tmp_path / "run-4")
    assert len(calls) == 6 and all("--aeroporto_x--" in call for call in calls)
    assert set(before) <= set(raw_keys(storage)) and len(raw_keys(storage)) == 16  # old revisions are preserved
    rows, _ = rows_by_key(storage, new_poles)
    assert not any(row["stale"] for row in rows)


def test_constitution_i_fr010_fr028_the_api_key_never_reaches_storage_output_or_error_messages(tmp_path, capsys):
    towns, poles = setup()
    dico_by_lat = {town["latitude"]: town["dico"] for town in towns}

    def transport(request):
        key = request.headers["x-goog-api-key"]
        origin = json.loads(request.content)["origins"][0]["waypoint"]["location"]["latLng"]["latitude"]
        if dico_by_lat[origin] == "0102":  # a server that echoes the credential back in its error body
            return reply(400, api_error("INVALID_ARGUMENT", f"bad request, key={key}", 400))
        if dico_by_lat[origin] == "0201":  # a transport failure whose message carries the credential
            raise httpx.ConnectError(f"connection to {request.url} failed for key={key}")
        return reply(200, routes_ok())

    catalog_path, storage = tmp_path / "sources.yml", MemoryStorage()
    write_catalog(catalog_path)
    code = cli.main(["--local", "--root", str(tmp_path), "--catalog", str(catalog_path), "--execute",
                     "--confirm-elements", "10", "--max-elements", "10"],
                    client=httpx.Client(transport=httpx.MockTransport(transport)), storage=storage,
                    env={"GOOGLE_ROUTES_API_KEY": KEY_SENTINEL}, municipalities=towns, poles=poles,
                    sleep=lambda seconds: None)
    captured = capsys.readouterr()
    assert code == 1  # failures were recorded, so the failure paths above really ran
    manifests = [json.loads(storage.get(key)) for key in storage.list_keys("manifests/google_distances/")]
    assert any(entry["status"] == "failed" for manifest in manifests for entry in manifest["datasets"])
    haystack = captured.out + captured.err + "".join(
        storage.get(key).decode("utf-8", errors="replace") for key in storage.list_keys())
    assert KEY_SENTINEL not in haystack
