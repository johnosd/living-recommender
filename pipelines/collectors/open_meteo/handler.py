"""Coleta o clima diário com estado independente por município."""
import json

from pipelines.collectors._shared.catalog import get_climate_source
from pipelines.collectors._shared.datasets import collect_items
from pipelines.collectors.open_meteo.fingerprint import fingerprint_open_meteo_response
from pipelines.collectors.open_meteo.municipalities import check_municipalities
from pipelines.collectors.open_meteo.validate import validate_open_meteo_response


def is_current_state(state: dict, source: dict) -> bool:
    period = f"{source['window']['start']}/{source['window']['end']}"
    return state.get("reference_period") == period and state.get("model") == source["model"]


def collect_open_meteo(catalog, *, municipalities, storage, fetcher, run_id, collected_at_utc,
                       work_dir, validator=None, max_municipalities=None, recollect=False):
    source = get_climate_source(catalog)
    check_municipalities(municipalities, source["expected_municipalities"])
    items = [{**town, "id": town["dico"], "collection_method": "api_json", "origin": source["api_url"],
              "window": source["window"], "variables": source["variables"], "model": source["model"]}
             for town in sorted(municipalities, key=lambda town: town["dico"])]

    def fetch(item, destination):
        meta = dict(fetcher(item, destination) or {})
        meta["reference_period"] = f"{source['window']['start']}/{source['window']['end']}"
        try:
            doc = json.loads(destination.read_text(encoding="utf-8"))
            if not isinstance(doc, dict):
                doc = {}
        except (ValueError, OSError):
            doc = {}
        meta["entry_extra"] = {
            "model": source["model"], "requested_lat": item["latitude"], "requested_lon": item["longitude"],
            "returned_lat": doc.get("latitude"), "returned_lon": doc.get("longitude"),
            "elevation_m": doc.get("elevation"), "timezone": doc.get("timezone"),
        }
        return meta

    return collect_items(source, items, source_id="open_meteo", storage=storage, fetcher=fetch,
                         validator=validator or validate_open_meteo_response, run_id=run_id,
                         collected_at_utc=collected_at_utc, work_dir=work_dir,
                         fingerprint=lambda _, path: fingerprint_open_meteo_response(path),
                         state_is_current=lambda _, state: is_current_state(state, source),
                         skip_current=not recollect, max_items=max_municipalities)
