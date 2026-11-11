"""Validação e leitura dos CSV do Pordata pelo rótulo das colunas.

O prefixo numérico varia entre datasets (`07. Escala`, `08. Escala`, `Max. 08. Escala`) e alguns
têm colunas extras (`Nome País (Europa)`), então posição e prefixo nunca servem de chave.
"""

import csv
import re
import unicodedata
from pathlib import Path
from typing import Any

SCOPE_LABEL = "Âmbito Geográfico"
MUNICIPALITY_SCOPE = "Município"
_PREFIX = re.compile(r"^\s*(?:Max\.\s*)?\d+\.\s*", re.IGNORECASE)


class PordataSchemaError(ValueError):
    """O CSV do Pordata não tem a estrutura esperada."""


def clean_label(column: str) -> str:
    """Remove o prefixo numérico e os espaços das pontas (`'08. Escala '` → `'Escala'`)."""
    return unicodedata.normalize("NFC", _PREFIX.sub("", column).strip())


def label_index(header: list[str]) -> dict[str, int]:
    """Posição da primeira coluna de cada rótulo limpo."""
    index: dict[str, int] = {}
    for position, column in enumerate(header):
        index.setdefault(clean_label(column), position)
    return index


def _open(path: Path):
    return path.open(encoding="utf-8-sig", newline="")


def validate_pordata_csv(dataset: dict[str, Any], path: Path) -> None:
    """Reprova HTML, arquivo vazio, rótulos ausentes e CSV sem nenhuma linha de município."""
    name = dataset["id"]
    try:
        with _open(path) as stream:
            first = stream.readline()
            if not first.strip():
                raise PordataSchemaError(f"{name}: arquivo vazio")
            if first.lstrip().startswith("<"):
                raise PordataSchemaError(f"{name}: resposta HTML no lugar do CSV")
            stream.seek(0)
            reader = csv.reader(stream)
            index = label_index(next(reader))
            missing = [label for label in dataset.get("expected_labels", []) if label not in index]
            if missing:
                raise PordataSchemaError(f"{name}: coluna ausente: {', '.join(missing)}")
            scope = index.get(SCOPE_LABEL)
            if scope is None:
                raise PordataSchemaError(f"{name}: coluna ausente: {SCOPE_LABEL}")
            if not any(len(row) > scope and row[scope] == MUNICIPALITY_SCOPE for row in reader):
                raise PordataSchemaError(f"{name}: nenhuma linha com {SCOPE_LABEL} = {MUNICIPALITY_SCOPE}")
    except UnicodeDecodeError as exc:
        raise PordataSchemaError(f"{name}: o arquivo não é UTF-8") from exc
