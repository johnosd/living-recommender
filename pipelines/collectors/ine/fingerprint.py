"""Impressão digital das respostas da API do INE.

A API devolve `DataExtracao` (o horário da chamada) e não envia `ETag` nem `Last-Modified`;
o `sha256` do arquivo bruto mudaria a cada coleta. A impressão digital ignora só esse campo.
Ver `sdd/specs/002-ingestao-pordata-ine/logic/ingestao-datasets.md` §2 e o risco R-008.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

# Campos que mudam a cada chamada sem que o INE tenha republicado nada. Um só lugar para estender.
VOLATILE_KEYS = frozenset({"DataExtracao"})


def _dump(node: Any) -> str:
    return json.dumps(node, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _canonical(node: Any) -> Any:
    if isinstance(node, dict):
        return {key: _canonical(value) for key, value in node.items() if key not in VOLATILE_KEYS}
    if isinstance(node, list):
        items = [_canonical(item) for item in node]
        if all(isinstance(item, dict) for item in items):
            # Listas de registros: a API devolve as mesmas linhas em ordem diferente entre chamadas
            # (observado na coleta real de 2026-11-11, criminalidade), sem mudança de conteúdo.
            items.sort(key=_dump)
        return items
    return node


def fingerprint_ine_response(path: str | Path) -> str:
    """SHA-256 do JSON canônico sem `DataExtracao` (horário da chamada)."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    return hashlib.sha256(_dump(_canonical(document)).encode("utf-8")).hexdigest()
