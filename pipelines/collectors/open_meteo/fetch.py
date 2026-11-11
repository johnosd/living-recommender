"""Pedido à API de arquivo do Open-Meteo, com classificação dos limites de cota (spec 003).

STUB do sdd-plan: implementado nas Fases 3 e 4 (T011, T017).
"""

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx


def make_open_meteo_fetcher(
    source: dict[str, Any],
    *,
    client: httpx.Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
    wait_on_limits: bool = True,
) -> Callable[[dict[str, Any], Path], dict[str, Any]]:
    """Devolve ``fetch(item, destino)``: uma requisição por município, para a janela inteira do catálogo.

    HTTP 429 de minuto ou de hora: espera e tenta de novo (``wait_on_limits``); se desligado ou esgotadas as
    tentativas, ou se o limite for o diário: levanta ``QuotaExhausted`` sem deixar arquivo em ``destino``.
    """
    raise NotImplementedError("not implemented: make_open_meteo_fetcher (T011, T017)")
