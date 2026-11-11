"""Distância entre o ponto municipal pedido e a célula devolvida pela fonte."""
import math

import pandas as pd

COLUMNS = ["dico", "requested_lat", "requested_lon", "returned_lat", "returned_lon", "elevation_m",
           "timezone", "distance_km", "diverged", "threshold_km", "source_run_id"]


def haversine_km(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat1), math.radians(lat2)
    dlat, dlon = b-a, math.radians(lon2-lon1)
    h = math.sin(dlat/2)**2 + math.cos(a)*math.cos(b)*math.sin(dlon/2)**2
    return 2 * 6371.0088 * math.asin(math.sqrt(min(1, max(0, h))))


def build_points(states, source):
    threshold = source.get("point_divergence_km", 25)
    rows = []
    for dico, state in sorted(states.items()):
        fields = {key: state[key] for key in COLUMNS[1:7]}
        distance = haversine_km(fields["requested_lat"], fields["requested_lon"],
                                fields["returned_lat"], fields["returned_lon"])
        rows.append({"dico": dico, **fields, "distance_km": distance, "diverged": distance > threshold,
                     "threshold_km": threshold, "source_run_id": state["run_id"]})
    return pd.DataFrame(rows, columns=COLUMNS)
