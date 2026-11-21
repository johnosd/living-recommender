"""Catálogo de polos (`config/poles.yml`): validação antes de qualquer cálculo (spec 009, FR-001/002/004)."""
import hashlib
import json
import math
import re
from pathlib import Path

import yaml

KINDS = ("cidade", "aeroporto", "sede_distrito", "capital_regional")
SCOPES = ("national", "district", "island")
GROUPS = ("continente", "madeira", "acores")
FIELDS = {"pole_id", "name", "kind", "routing_group", "scope", "dico", "latitude", "longitude",
          "district_or_island", "source_ref"}
POLE_ID = re.compile(r"[a-z0-9_]+")
LAT_RANGE, LON_RANGE = (29, 43), (-32, -6)  # a mesma caixa do clima: Portugal e as regiões autónomas


class PoleError(ValueError):
    """Catálogo de polos inválido; a mensagem nomeia o polo."""


def _coordinate(value, low, high) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def _check(raw, pole_id: str, towns: dict[str, dict]) -> dict:
    unknown = sorted(set(raw) - FIELDS)
    if unknown:
        raise PoleError(f"{pole_id}: campo desconhecido: {', '.join(unknown)}")
    if not isinstance(raw.get("name"), str) or not raw["name"].strip():
        raise PoleError(f"{pole_id}: name obrigatório")
    kind, group, scope = raw.get("kind"), raw.get("routing_group"), raw.get("scope")
    if kind not in KINDS:
        raise PoleError(f"{pole_id}: kind desconhecido: {kind!r}")
    if group not in GROUPS:
        raise PoleError(f"{pole_id}: routing_group desconhecido: {group!r}")
    if scope not in SCOPES:
        raise PoleError(f"{pole_id}: scope desconhecido: {scope!r}")
    if scope == "national" and group != "continente":
        raise PoleError(f"{pole_id}: scope national só vale no continente")
    if scope == "district" and kind != "sede_distrito":
        raise PoleError(f"{pole_id}: scope district só vale para sede_distrito")
    if kind == "sede_distrito" and scope != "district":
        raise PoleError(f"{pole_id}: sede_distrito exige scope district")
    if scope == "island" and group == "continente":
        raise PoleError(f"{pole_id}: scope island exige madeira ou acores")
    resolved = {"pole_id": pole_id, "name": raw["name"], "kind": kind, "routing_group": group, "scope": scope,
                "dico": None, "latitude": None, "longitude": None, "district_or_island": None,
                "source_ref": raw.get("source_ref")}
    if kind == "aeroporto":
        if raw.get("dico") is not None:
            raise PoleError(f"{pole_id}: aeroporto não referencia município")
        lat, lon = raw.get("latitude"), raw.get("longitude")
        if not (_coordinate(lat, *LAT_RANGE) and _coordinate(lon, *LON_RANGE)):
            raise PoleError(f"{pole_id}: coordenadas ausentes ou fora de Portugal: {lat}, {lon}")
        if not isinstance(raw.get("source_ref"), str) or not raw["source_ref"].strip():
            raise PoleError(f"{pole_id}: source_ref obrigatório em aeroporto")
        district = raw.get("district_or_island")
        if scope == "island" and (not isinstance(district, str) or not district):
            raise PoleError(f"{pole_id}: aeroporto de ilha exige district_or_island")
        resolved.update(latitude=float(lat), longitude=float(lon), district_or_island=district)
        return resolved
    if raw.get("latitude") is not None or raw.get("longitude") is not None:
        raise PoleError(f"{pole_id}: {kind} usa o ponto do município; não declare coordenadas")
    dico = raw.get("dico")
    town = towns.get(dico) if isinstance(dico, str) else None
    if town is None:
        raise PoleError(f"{pole_id}: dico inexistente na dimensão: {dico!r}")
    if town["routing_group"] != group:
        raise PoleError(f"{pole_id}: routing_group {group} diverge do município {dico} ({town['routing_group']})")
    resolved.update(dico=dico, latitude=town["latitude"], longitude=town["longitude"],
                    district_or_island=town["district_or_island"])
    return resolved


def resolve_poles(raw_poles: list[dict], municipalities: list[dict]) -> list[dict]:
    """Valida todos os polos e resolve `dico` em coordenadas; qualquer violação rejeita o catálogo inteiro."""
    if not isinstance(raw_poles, list) or not raw_poles:
        raise PoleError("o catálogo de polos precisa ter ao menos um polo")
    towns = {town["dico"]: town for town in municipalities}
    seen, resolved = set(), []
    for raw in raw_poles:
        pole_id = raw.get("pole_id") if isinstance(raw, dict) else None
        if not isinstance(pole_id, str) or not POLE_ID.fullmatch(pole_id):
            raise PoleError(f"pole_id inválido: {pole_id!r}")
        if pole_id in seen:
            raise PoleError(f"{pole_id}: pole_id repetido")
        seen.add(pole_id)
        resolved.append(_check(raw, pole_id, towns))
    return sorted(resolved, key=lambda pole: pole["pole_id"])


def load_poles(path: Path, municipalities: list[dict]) -> list[dict]:
    with Path(path).open(encoding="utf-8") as stream:
        document = yaml.safe_load(stream)
    if not isinstance(document, dict) or document.get("version") != 1 or not isinstance(document.get("poles"), list):
        raise PoleError("poles.yml precisa ter version: 1 e a lista poles")
    return resolve_poles(document["poles"], municipalities)


def poles_catalog_version(poles: list[dict]) -> str:
    """SHA-256 canônico dos polos resolvidos (proveniência `poles_catalog_version`)."""
    ordered = sorted(poles, key=lambda pole: pole["pole_id"])
    canonical = json.dumps(ordered, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
