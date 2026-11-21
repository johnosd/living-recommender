"""Pares elegíveis município–polo–modo. Stub do sdd-plan: o executor implementa (logic/pares-e-estados.md)."""


def pair_id(dico: str, pole_id: str, mode: str) -> str:
    """`{dico}--{pole_id}--{mode}`: identifica o item de coleta e o estado vigente."""
    raise NotImplementedError("spec 009: T009")


def route_pairs(municipalities: list[dict], poles: list[dict]) -> list[dict]:
    """Pares dos modos `driving` e `transit`, com `identity=True` quando origem e destino coincidem."""
    raise NotImplementedError("spec 009: T009")
