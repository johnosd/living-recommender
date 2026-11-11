"""Validação do bruto do Open-Meteo antes de virar estado vigente (spec 003).

STUB do sdd-plan: implementado na Fase 3 (T008).
"""

from pathlib import Path
from typing import Any


def validate_open_meteo_response(item: dict[str, Any], path: Path) -> None:
    """Levanta ``ValueError`` se a resposta não for um bruto aceitável (FR-009).

    ``item`` traz a fonte já mesclada (``window``, ``variables``); ver ``logic/coleta-clima.md`` §4.
    """
    raise NotImplementedError("not implemented: validate_open_meteo_response (T008)")
