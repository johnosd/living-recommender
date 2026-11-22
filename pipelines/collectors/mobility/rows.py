"""Linhas de distância com estado por par (spec 009, logic/pares-e-estados.md §5)."""
from pipelines.collectors._shared.dataset_manifest import latest_dataset_states
from pipelines.collectors.mobility.catalog import SOURCE_ID, mobility_source
from pipelines.collectors.mobility.pairs import build_items, route_pairs
from pipelines.collectors.mobility.poles import poles_catalog_version
from pipelines.collectors.mobility.state import is_current_state, latest_attempts
from pipelines.collectors.mobility.straight_line import straight_line_rows

STATUSES = ("ok", "sem_rota", "falha", "pendente")
# A linha reta deriva da dimensão CAOP e dos polos; os tempos de carro (e a identidade) são do Google.
LINE_SOURCE_ID = "caop"


def _blank(pair: dict, mode: str) -> dict:
    return {"dico": pair["dico"], "pole_id": pair["pole_id"], "mode": mode, "km": None, "minutes": None,
            "status": "pendente", "no_route_reason": None, "error": None, "method": "google_routes_v2",
            "departure_time": None, "stale": False, "calculated_at_utc": None, "source_run_id": None}


def _route_row(pair: dict, item: dict | None, state: dict | None, attempt: dict | None) -> dict:
    row = _blank(pair, pair["mode"])
    if pair["identity"]:
        return {**row, "km": 0.0, "minutes": 0.0, "status": "ok", "method": "identity"}
    row["departure_time"] = item.get("departure_time") if item else None
    if state is not None:
        row.update(calculated_at_utc=state["collected_at_utc"], source_run_id=state["run_id"],
                   stale=not is_current_state(item, state))
        if state.get("route_status") == "ROUTE_NOT_FOUND":
            return {**row, "status": "sem_rota", "no_route_reason": "ROUTE_NOT_FOUND"}
        return {**row, "status": "ok", "km": state["distance_m"] / 1000, "minutes": state["duration_s"] / 60}
    if attempt is not None and attempt["status"] == "failed":
        return {**row, "status": "falha", "error": attempt.get("error")}
    return row


def build_distance_rows(catalog, *, municipalities, poles, storage, processed_at_utc) -> list[dict]:
    """Uma linha por par esperado e modo (inclui `straight_line`): ok, sem_rota, falha ou pendente."""
    source = mobility_source(catalog)
    modes = tuple(source["modes"])
    items = {item["id"]: item for item in build_items(source, municipalities, poles)}
    states = latest_dataset_states(storage, SOURCE_ID)
    attempts = latest_attempts(storage)
    caop = (catalog.get("sources", catalog) or {}).get("caop") or {}
    towns = {town["dico"]: town for town in municipalities}
    version = poles_catalog_version(poles)
    rows = [{**row, "departure_time": None, "stale": False, "calculated_at_utc": None, "source_run_id": None,
             "source_id": LINE_SOURCE_ID} for row in straight_line_rows(municipalities, poles)]
    for row in rows:  # a linha reta deriva da CAOP e dos polos: leva a licença da dimensão
        row.update(license_id=towns[row["dico"]].get("license_id") or caop.get("license_id"),
                   attribution=None, usage_restriction=None)
    for pair in route_pairs(municipalities, poles, modes):
        row = _route_row(pair, items.get(pair["id"]), states.get(pair["id"]), attempts.get(pair["id"]))
        row.update(source_id=SOURCE_ID, license_id=source["license_id"], attribution=source["attribution"],
                   usage_restriction=source.get("usage_restriction"))
        rows.append(row)
    for row in rows:
        row.update(caop_version=towns[row["dico"]].get("caop_version"), poles_catalog_version=version,
                   reference_period=source["reference_period"], processed_at_utc=processed_at_utc)
    return sorted(rows, key=lambda row: (row["dico"], row["pole_id"], row["mode"]))
