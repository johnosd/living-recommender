"""Pares elegíveis município–polo–modo e itens de coleta (spec 009, logic/pares-e-estados.md §2–§4)."""

SUPPORTED_MODES = ("driving", "transit")


def pair_id(dico: str, pole_id: str, mode: str) -> str:
    """`{dico}--{pole_id}--{mode}`: identifica o item de coleta e o estado vigente."""
    return f"{dico}--{pole_id}--{mode}"


def eligible(town: dict, pole: dict) -> bool:
    """Mesmo grupo de roteamento e escopo compatível; pares entre ilhas diferentes não existem (seriam pagos à toa)."""
    if town["routing_group"] != pole["routing_group"]:
        return False
    if pole["scope"] == "national":
        return True
    return town["district_or_island"] == pole["district_or_island"]


def is_identity(town: dict, pole: dict) -> bool:
    """O município do próprio polo: origem e destino são o mesmo ponto, então a distância é exatamente zero."""
    return pole["kind"] != "aeroporto" and pole["dico"] == town["dico"]


def route_pairs(municipalities: list[dict], poles: list[dict], modes=SUPPORTED_MODES) -> list[dict]:
    """Pares dos modos de rota, com `identity=True` quando origem e destino coincidem; ordenados por `id`."""
    pairs = []
    for town in municipalities:
        for pole in poles:
            if not eligible(town, pole):
                continue
            for mode in modes:
                pairs.append({"id": pair_id(town["dico"], pole["pole_id"], mode), "dico": town["dico"],
                              "pole_id": pole["pole_id"], "mode": mode, "identity": is_identity(town, pole)})
    return sorted(pairs, key=lambda pair: pair["id"])


def make_item(pair: dict, town: dict, pole: dict, source: dict) -> dict:
    """Item de `collect_items`; nunca carrega a chave."""
    mode = source["modes"][pair["mode"]]
    return {
        "id": pair["id"], "dico": pair["dico"], "pole_id": pair["pole_id"], "mode": pair["mode"],
        "collection_method": "api_json", "origin": source["api_url"],
        "origin_lat": town["latitude"], "origin_lon": town["longitude"],
        "dest_lat": pole["latitude"], "dest_lon": pole["longitude"],
        "travel_mode": mode["travel_mode"], "routing_preference": mode.get("routing_preference"),
        "departure_time": mode.get("departure_time"),
    }


def build_items(source: dict, municipalities: list[dict], poles: list[dict]) -> list[dict]:
    """Itens dos pares consultáveis (sem identidade) nos modos habilitados do catálogo, ordenados por `id`."""
    towns = {town["dico"]: town for town in municipalities}
    by_id = {pole["pole_id"]: pole for pole in poles}
    return [make_item(pair, towns[pair["dico"]], by_id[pair["pole_id"]], source)
            for pair in route_pairs(municipalities, poles, tuple(source["modes"])) if not pair["identity"]]
