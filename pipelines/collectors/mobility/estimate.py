"""Estimativa de pares, elementos e custo, sem rede e sem chave (spec 009, FR-008/009, logic §7)."""
from collections import Counter

from pipelines.collectors._shared.dataset_manifest import latest_dataset_states
from pipelines.collectors.mobility.catalog import SOURCE_ID, mobility_source
from pipelines.collectors.mobility.pairs import build_items, route_pairs
from pipelines.collectors.mobility.state import is_current_state


def estimate_run(catalog: dict, *, municipalities: list[dict], poles: list[dict], storage) -> dict:
    """Pares novos e desatualizados viram elementos cobrados; os atuais e as identidades não custam nada."""
    source = mobility_source(catalog)
    modes = tuple(source["modes"])
    pairs = route_pairs(municipalities, poles, modes)
    states = latest_dataset_states(storage, SOURCE_ID)
    new = stale = 0
    elements: Counter = Counter({mode: 0 for mode in modes})
    for item in build_items(source, municipalities, poles):
        state = states.get(item["id"])
        if state is not None and is_current_state(item, state):
            continue
        stale += state is not None
        new += state is None
        elements[item["mode"]] += 1
    cost = worst = 0.0
    for mode, count in elements.items():
        price = source["pricing"][mode]
        cost += max(0, count - price["free_monthly"]) * price["usd_per_1000"] / 1000
        worst += count * price["usd_per_1000"] / 1000
    return {"pairs_total": len(pairs), "identity": sum(pair["identity"] for pair in pairs), "new": new,
            "stale": stale, "elements": dict(elements), "elements_total": sum(elements.values()),
            "ceiling": source["max_elements_per_run"], "cost_usd_estimate": cost, "cost_usd_worst_case": worst,
            "pricing_verified_on": source.get("pricing_verified_on")}
