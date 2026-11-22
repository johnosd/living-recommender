"""Coleta por par município–polo–modo, retomável, sobre o motor `collect_items` da spec 003 (spec 009)."""
import json

from pipelines.collectors._shared.datasets import collect_items
from pipelines.collectors.mobility.catalog import FIELD_MASK, SOURCE_ID, mobility_source
from pipelines.collectors.mobility.pairs import build_items
from pipelines.collectors.mobility.poles import poles_catalog_version
from pipelines.collectors.mobility.state import is_current_state, pair_signature
from pipelines.collectors.mobility.validate import validate_routes_response


def _duration_seconds(value):
    if isinstance(value, str) and value.endswith("s"):
        try:
            seconds = float(value[:-1])
        except ValueError:
            return None
        return int(seconds) if seconds.is_integer() else seconds
    return None


def _element(path) -> dict:
    """Primeiro elemento da resposta, ou `{}` se o arquivo não for uma resposta válida (o validador decide)."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    return document[0] if isinstance(document, list) and document and isinstance(document[0], dict) else {}


def collect_mobility(catalog, *, municipalities, poles, storage, fetcher, run_id, collected_at_utc, work_dir,
                     validator=None, max_elements=None, redact=None):
    """Mesmo retorno de `collect_items`: status, datasets, remaining, quota_exhausted, up_to_date."""
    source = mobility_source(catalog)
    items = build_items(source, municipalities, poles)
    version = poles_catalog_version(poles)
    validate = validator or validate_routes_response

    def checked(item, path):
        try:
            validate(item, path)
        except Exception as exc:
            if redact is None:
                raise
            raise ValueError(redact(str(exc))) from None

    def fetch(item, destination):
        meta = dict(fetcher(item, destination) or {})
        meta["reference_period"] = source["reference_period"]
        element = _element(destination)
        meta["entry_extra"] = {
            "pair_signature": pair_signature(item), "mode": item["mode"], "pole_id": item["pole_id"],
            "dico": item["dico"], "requested_origin": [item["origin_lat"], item["origin_lon"]],
            "requested_destination": [item["dest_lat"], item["dest_lon"]], "travel_mode": item["travel_mode"],
            "routing_preference": item.get("routing_preference"), "departure_time": item.get("departure_time"),
            "api_url": item["origin"], "field_mask": FIELD_MASK, "route_status": element.get("condition"),
            "distance_m": element.get("distanceMeters"), "duration_s": _duration_seconds(element.get("duration")),
            "returned_coordinates": "unavailable", "poles_catalog_version": version,
        }
        return meta

    return collect_items(source, items, source_id=SOURCE_ID, storage=storage, fetcher=fetch, validator=checked,
                         run_id=run_id, collected_at_utc=collected_at_utc, work_dir=work_dir,
                         state_is_current=is_current_state, skip_current=True, max_items=max_elements)
