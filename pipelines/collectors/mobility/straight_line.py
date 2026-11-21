"""Distância em linha reta (haversine) do município a cada polo, sem API (spec 009, FR-005/006)."""
from pipelines.collectors.open_meteo.points import haversine_km


def straight_line_rows(municipalities: list[dict], poles: list[dict]) -> list[dict]:
    """Uma linha por município e polo, modo `straight_line`; vale para todo par, inclusive entre ilhas."""
    rows = []
    for town in sorted(municipalities, key=lambda item: item["dico"]):
        for pole in sorted(poles, key=lambda item: item["pole_id"]):
            same_point = pole["kind"] != "aeroporto" and pole["dico"] == town["dico"]
            km = 0.0 if same_point else haversine_km(town["latitude"], town["longitude"],
                                                      pole["latitude"], pole["longitude"])
            rows.append({"dico": town["dico"], "pole_id": pole["pole_id"], "mode": "straight_line", "km": km,
                         "minutes": None, "status": "ok", "no_route_reason": None, "error": None,
                         "method": "haversine"})
    return rows
