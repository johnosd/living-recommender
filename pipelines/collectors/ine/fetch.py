"""Pedido à API de indicadores do INE (`pindica.jsp`) e metadados de cada coleta."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

LANG = "PT"


def build_url(dataset: dict[str, Any]) -> str:
    """URL do indicador, com os parâmetros do catálogo (`Dim1=T` todos os períodos, `Dim2=lvl@5` município)."""
    query = {"op": 2, "varcd": dataset["indicator"], **dataset.get("params", {}), "lang": LANG}
    return f"{dataset['api_url']}?{urlencode(query, safe='@,')}"


def make_ine_fetcher(downloader: Callable[[str, Path], Any]) -> Callable[[dict[str, Any], Path], dict[str, Any]]:
    """Baixa o indicador e devolve o período e a data de publicação informados pela própria resposta."""

    def fetch(dataset: dict[str, Any], destination: Path) -> dict[str, Any]:
        downloader(build_url(dataset), destination)
        meta: dict[str, Any] = dict(getattr(downloader, "last_headers", None) or {})
        try:  # leitura leve; se o JSON for inválido, quem reprova é o validador
            document = json.loads(Path(destination).read_text(encoding="utf-8"))
            document = document[0] if isinstance(document, list) else document
            meta["reference_period"] = str(document["UltimoPref"]) if document.get("UltimoPref") else None
            meta["source_release_date"] = document.get("DataUltimoAtualizacao")
        except (ValueError, KeyError, IndexError, AttributeError, TypeError):
            pass
        return meta

    return fetch
