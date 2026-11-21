"""Catálogo de polos (`config/poles.yml`). Stub do sdd-plan: o executor implementa."""
from pathlib import Path


def resolve_poles(raw_poles: list[dict], municipalities: list[dict]) -> list[dict]:
    """Valida os polos e resolve `dico` em coordenadas; rejeita tudo antes de qualquer cálculo (FR-002, FR-004)."""
    raise NotImplementedError("spec 009: T008")


def load_poles(path: Path, municipalities: list[dict]) -> list[dict]:
    """Lê o YAML de polos e chama `resolve_poles`."""
    raise NotImplementedError("spec 009: T008")


def poles_catalog_version(poles: list[dict]) -> str:
    """SHA-256 canônico dos polos resolvidos (proveniência `poles_catalog_version`)."""
    raise NotImplementedError("spec 009: T008")
