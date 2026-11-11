"""Impressão digital do bruto do Open-Meteo: JSON canônico sem os metadados voláteis (spec 003).

STUB do sdd-plan: implementado na Fase 3 (T009).
"""

from pathlib import Path


def fingerprint_open_meteo_response(path: Path) -> str:
    """SHA-256 do JSON canônico sem ``generationtime_ms``; ver ``logic/coleta-clima.md`` §3."""
    raise NotImplementedError("not implemented: fingerprint_open_meteo_response (T009)")
