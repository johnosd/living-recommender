"""Coleta do clima diário do Open-Meteo, uma unidade por município (spec 003).

STUB do sdd-plan: o corpo é implementado na Fase 3 (T010). Ver
`sdd/specs/003-ingestao-clima-open-meteo/logic/coleta-clima.md`.
"""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any


def collect_open_meteo(
    catalog: dict[str, Any],
    *,
    municipalities: Sequence[dict[str, Any]],
    storage: Any,
    fetcher: Callable[[dict[str, Any], Path], Any],
    run_id: str,
    collected_at_utc: str,
    work_dir: Path,
    validator: Callable[[dict[str, Any], Path], None] | None = None,
    max_municipalities: int | None = None,
    recollect: bool = False,
) -> dict[str, Any]:
    """Coleta o clima de cada município pendente e grava o manifest v2.

    ``municipalities``: ``[{"dico", "name", "latitude", "longitude"}]`` (a dimensão da spec 001).
    ``fetcher(item, destino)``: baixa a resposta do município para ``destino``.
    Retorna ``{"status", "run_id", "manifest_key", "datasets", "skipped_current", "remaining",
    "quota_exhausted", "up_to_date"}``.
    """
    raise NotImplementedError("not implemented: collect_open_meteo (T010)")
