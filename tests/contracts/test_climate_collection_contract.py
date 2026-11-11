"""Locked contracts for the Open-Meteo climate ingestion (spec 003).

Only public boundaries are exercised: `collect_open_meteo`, `make_open_meteo_fetcher` (over an injected
`httpx` mock transport) and `read_climate_response`, with injected fetcher/storage and no network.
"""

import datetime
import hashlib
import json

import httpx
import pytest

from pipelines.collectors._shared.datasets import QuotaExhausted
from pipelines.collectors.open_meteo.fetch import make_open_meteo_fetcher
from pipelines.collectors.open_meteo.handler import collect_open_meteo
from pipelines.collectors.open_meteo.transform import read_climate_response
from tests.fixtures.open_meteo.responses import (
    DAY_LIMIT,
    END,
    MINUTE_LIMIT,
    START,
    VARIABLES,
    MemoryStorage,
    catalog,
    error_response,
    municipalities,
    open_meteo_response,
)

PERIOD = f"{START}/{END}"


def run(storage, run_id, tmp_path, towns, fetcher, *, recollect=False):
    return collect_open_meteo(
        catalog(len(towns)),
        municipalities=towns,
        storage=storage,
        fetcher=fetcher,
        run_id=run_id,
        collected_at_utc="2026-11-11T12:00:00Z",
        work_dir=tmp_path / run_id,
        recollect=recollect,
    )


def by_id(result):
    return {entry["dataset_id"]: entry for entry in result["datasets"]}


def raw_keys(storage):
    return {key for key in storage.list_keys() if key.startswith("raw/")}


def test_us1_ac1_ac2_fr005_fr006_fr007_each_municipality_is_stored_and_recollecting_is_unchanged(tmp_path):
    storage, towns, calls = MemoryStorage(), municipalities(4), []

    def fetch(item, destination):
        calls.append(item["id"])
        # the grid point differs from the requested one, and `generationtime_ms` changes on every call
        destination.write_text(
            open_meteo_response(latitude=item["latitude"] + 0.01, longitude=item["longitude"],
                                generation_ms=1.5 * len(calls)),
            encoding="utf-8",
        )

    first = run(storage, "run-1", tmp_path, towns, fetch)
    assert first["status"] == "changed"
    manifest = json.loads(storage.get("manifests/open_meteo/run-1.json"))
    assert manifest["source_id"] == "open_meteo" and manifest["run_id"] == "run-1"
    assert manifest["license_id"] == "CC-BY-4.0"
    assert manifest["collected_at_utc"] == "2026-11-11T12:00:00Z"
    entries = {entry["dataset_id"]: entry for entry in manifest["datasets"]}
    assert set(entries) == {town["dico"] for town in towns}
    for town in towns:
        entry, dico = entries[town["dico"]], town["dico"]
        assert entry["status"] == "changed"
        assert entry["key"] == f"raw/source=open_meteo/dataset={dico}/run_id=run-1/{dico}.json"
        raw = storage.get(entry["key"])
        assert entry["sha256"] == hashlib.sha256(raw).hexdigest() and entry["bytes"] == len(raw)
        assert entry["reference_period"] == PERIOD and entry["model"] == "era5"
        assert (entry["requested_lat"], entry["requested_lon"]) == (town["latitude"], town["longitude"])
        assert entry["returned_lat"] == pytest.approx(town["latitude"] + 0.01)
        assert entry["returned_lon"] == pytest.approx(town["longitude"])
    raw_after_first = raw_keys(storage)

    second = run(storage, "run-2", tmp_path, towns, fetch, recollect=True)
    assert second["status"] == "unchanged"
    assert {entry["status"] for entry in second["datasets"]} == {"unchanged"}
    assert raw_keys(storage) == raw_after_first
    assert len(calls) == 8  # a recoleta consultou a fonte de novo


def test_us1_ac4_ac5_fr007_fr008_invalid_responses_fail_per_municipality_without_partial_raw_nor_state(tmp_path):
    storage, towns, calls = MemoryStorage(), municipalities(5), []
    broken = {
        "0002": open_meteo_response(drop=("temperature_2m_min",)),
        "0003": open_meteo_response(short_by=1),
        "0004": error_response("Parameter 'daily' is invalid"),
        "0005": open_meteo_response(nulls={"precipitation_sum": "all"}),
    }

    def fetch_with_failures(item, destination):
        calls.append(item["id"])
        destination.write_text(broken.get(item["id"], open_meteo_response()), encoding="utf-8")

    first = run(storage, "run-1", tmp_path, towns, fetch_with_failures)
    entries = by_id(first)
    assert first["status"] == "partial"
    assert entries["0001"]["status"] == "changed"
    for dico in ("0002", "0003", "0004", "0005"):
        assert entries[dico]["status"] == "failed" and entries[dico]["error"]
    assert "temperature_2m_min" in entries["0002"]["error"]
    assert "Parameter 'daily' is invalid" in entries["0004"]["error"]
    assert "precipitation_sum" in entries["0005"]["error"]
    assert raw_keys(storage) == {entries["0001"]["key"]}  # nenhum arquivo parcial dos reprovados
    assert json.loads(storage.get("manifests/open_meteo/run-1.json"))["status"] == "partial"

    calls.clear()

    def fetch_ok(item, destination):
        calls.append(item["id"])
        destination.write_text(open_meteo_response(), encoding="utf-8")

    second = run(storage, "run-2", tmp_path, towns, fetch_ok)
    assert calls == ["0002", "0003", "0004", "0005"]  # 0001 já tem estado vigente, vindo da execução parcial
    assert second["status"] == "changed"
    assert {entry["status"] for entry in second["datasets"]} == {"changed"}


def test_us2_ac1_ac2_ac4_fr012_fr013_fr015_quota_stop_marks_pending_and_resume_fetches_only_pending(tmp_path):
    storage, towns, calls, budget = MemoryStorage(), municipalities(6), [], {"left": 3}

    def fetch(item, destination):
        calls.append(item["id"])
        if budget["left"] == 0:
            raise QuotaExhausted("daily")
        budget["left"] -= 1
        destination.write_text(open_meteo_response(), encoding="utf-8")

    first = run(storage, "run-1", tmp_path, towns, fetch)
    entries = by_id(first)
    assert first["status"] == "partial" and first["quota_exhausted"] is True
    assert [entries[dico]["status"] for dico in ("0001", "0002", "0003")] == ["changed"] * 3
    for dico in ("0004", "0005", "0006"):
        assert entries[dico]["status"] == "pending" and "daily" in entries[dico]["error"]
    assert calls == ["0001", "0002", "0003", "0004"]  # parou na primeira recusa: 0005 e 0006 nem foram tentados
    assert raw_keys(storage) == {entries[dico]["key"] for dico in ("0001", "0002", "0003")}
    manifest = json.loads(storage.get("manifests/open_meteo/run-1.json"))
    assert manifest["status"] == "partial"
    assert {e["dataset_id"]: e["status"] for e in manifest["datasets"]}["0006"] == "pending"

    calls.clear()
    budget["left"] = 10
    second = run(storage, "run-2", tmp_path, towns, fetch)
    assert calls == ["0004", "0005", "0006"]  # só os pendentes; os três gravados não geram chamada
    assert second["status"] == "changed" and second["quota_exhausted"] is False
    assert second["skipped_current"] == 3 and second["remaining"] == 0

    calls.clear()
    third = run(storage, "run-3", tmp_path, towns, fetch)
    assert calls == [] and third["up_to_date"] is True and third["skipped_current"] == 6
    assert third["manifest_key"] is None
    assert "manifests/open_meteo/run-3.json" not in storage.list_keys()


def test_us2_ac3_fr003_fr012_minute_limit_waits_and_daily_limit_stops_without_waiting(tmp_path):
    source = catalog(1)["open_meteo"]
    item = {"id": "0001", "name": "Município 0001", "latitude": 37.01, "longitude": -8.01}
    json_type = {"content-type": "application/json"}

    def make_client(*replies):
        queue, requests = iter(replies), []

        def handler(request):
            requests.append(request)
            return next(queue)

        return httpx.Client(transport=httpx.MockTransport(handler)), requests

    ok = httpx.Response(200, text=open_meteo_response(), headers=json_type)
    minute = httpx.Response(429, text=error_response(MINUTE_LIMIT), headers=json_type)
    daily = httpx.Response(429, text=error_response(DAY_LIMIT), headers=json_type)

    client, requests = make_client(minute, ok)
    sleeps = []
    destination = tmp_path / "a.json"
    make_open_meteo_fetcher(source, client=client, sleep=sleeps.append)(item, destination)
    assert len(requests) == 2 and len(sleeps) == 1 and 0 < sleeps[0] <= 120  # esperou o minuto e tentou de novo
    assert json.loads(destination.read_text(encoding="utf-8"))["daily"]["time"][0] == START
    params = requests[0].url.params
    assert (params["latitude"], params["longitude"]) == ("37.01", "-8.01")
    assert (params["start_date"], params["end_date"], params["models"]) == (START, END, "era5")
    assert params["timezone"] == "auto" and set(params["daily"].split(",")) == set(VARIABLES)
    assert "living-recommender" in requests[0].headers["user-agent"]

    client, requests = make_client(daily)
    sleeps, destination = [], tmp_path / "b.json"
    with pytest.raises(QuotaExhausted):
        make_open_meteo_fetcher(source, client=client, sleep=sleeps.append)(item, destination)
    assert sleeps == [] and len(requests) == 1 and not destination.exists()  # o limite diário não espera

    client, requests = make_client(minute)
    sleeps, destination = [], tmp_path / "c.json"
    with pytest.raises(QuotaExhausted):
        make_open_meteo_fetcher(source, client=client, sleep=sleeps.append, wait_on_limits=False)(item, destination)
    assert sleeps == [] and not destination.exists()


def test_us3_ac2_ac4_ac5_fr016_fr017_staging_keeps_nulls_local_dates_and_source_units(tmp_path):
    path = tmp_path / "0001.json"
    path.write_text(
        open_meteo_response(start="2025-03-29", end="2025-03-31", timezone="Atlantic/Azores",
                            utc_offset_seconds=-3600, nulls={"precipitation_sum": {1}}),
        encoding="utf-8",
    )
    document = json.loads(path.read_text(encoding="utf-8"))

    frame = read_climate_response(path)
    assert list(frame.columns) == ["variable", "date", "value", "unit"]
    assert len(frame) == len(VARIABLES) * 3 and set(frame["variable"]) == set(VARIABLES)
    expected_days = [datetime.date(2025, 3, 29), datetime.date(2025, 3, 30), datetime.date(2025, 3, 31)]
    assert sorted(set(frame["date"])) == expected_days  # o dia local da fonte, sem deslocamento de fuso
    assert all(type(day) is datetime.date for day in frame["date"])
    gap = frame[(frame["variable"] == "precipitation_sum") & (frame["date"] == expected_days[1])]
    assert len(gap) == 1 and gap["value"].isna().all()  # ausente continua ausente, nunca 0
    assert int(frame["value"].isna().sum()) == 1
    units = dict(zip(frame["variable"], frame["unit"], strict=True))
    assert units == VARIABLES  # unidades da fonte, sem conversão
    sun = frame[frame["variable"] == "sunshine_duration"].sort_values("date")["value"].tolist()
    assert sun == document["daily"]["sunshine_duration"]
