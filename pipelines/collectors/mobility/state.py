"""Estado por par: assinatura, obsolescência e última tentativa (spec 009, logic/pares-e-estados.md §4–§5)."""
import hashlib
import json
from datetime import datetime

from pipelines.collectors._shared.dataset_manifest import SCHEMA_VERSION
from pipelines.collectors.mobility.catalog import FIELD_MASK, SOURCE_ID


def pair_signature(item: dict) -> str:
    """Impressão digital do que define o par; mudar qualquer campo torna o estado antigo desatualizado."""
    canonical = json.dumps({
        "origin": [item["origin_lat"], item["origin_lon"]], "destination": [item["dest_lat"], item["dest_lon"]],
        "mode": item["mode"], "travel_mode": item["travel_mode"],
        "routing_preference": item.get("routing_preference"), "departure_time": item.get("departure_time"),
        "api_url": item["origin"], "field_mask": FIELD_MASK,
    }, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def is_current_state(item: dict, state: dict) -> bool:
    return state.get("pair_signature") == pair_signature(item)


def latest_attempts(storage, source_id: str = SOURCE_ID) -> dict[str, dict]:
    """Última entrada de cada par entre os manifests da fonte, de qualquer status (inclui `failed` e `pending`)."""
    prefix = f"manifests/{source_id}/"
    best: dict[str, tuple[tuple[datetime, str], dict]] = {}
    for key in sorted(storage.list_keys()):
        if not key.startswith(prefix) or not key.endswith(".json"):
            continue
        manifest = json.loads(storage.get(key))
        if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("source_id") != source_id:
            continue
        order = (datetime.fromisoformat(manifest["collected_at_utc"]), manifest["run_id"])
        for entry in manifest.get("datasets", []):
            current = best.get(entry["dataset_id"])
            if current is None or order > current[0]:
                best[entry["dataset_id"]] = (order, {**entry, "run_id": manifest["run_id"],
                                                     "collected_at_utc": manifest["collected_at_utc"]})
    return {dataset_id: attempt for dataset_id, (_, attempt) in best.items()}
