"""Leitura das planilhas de correspondência do INE: a única parte que abre o arquivo (spec 004).

`validate_crosswalk_table` e `read_crosswalk_table` usam `load_rows`; assim os dois nunca divergem.
Regras em `sdd/specs/004-correspondencia-freguesias/logic/derivacao-correspondencia.md` §1 e `research.md` R1-R3.
"""

import re
import unicodedata
import zipfile
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

CODE = re.compile(r"[0-9A-Z]{6}")
PARTIAL = re.compile(r"\(parte\)\s*$", re.IGNORECASE)


class CrosswalkSchemaError(ValueError):
    """A planilha do INE não tem a estrutura esperada."""


def normalize_label(value: Any) -> str:
    """Rótulo comparável: NFC, espaços colapsados, sem espaços nas pontas, `casefold` (o INE usa dois espaços)."""
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", str(value))).strip().casefold() if value is not None else ""


def normalize_text(value: Any) -> str:
    """Designação limpa: NFC, espaços colapsados e sem espaços nas pontas; célula vazia vira texto vazio."""
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", str(value))).strip() if value is not None else ""


def is_partial(name: str) -> bool:
    """A designação pré-2013 termina em `(parte)` (a freguesia foi incorporada só em parte)."""
    return bool(PARTIAL.search(name))


def normalize_code(value: Any, *, where: str) -> tuple[str, bool]:
    """Devolve ``(código, era_numérico)``. Inteiro de exatamente 6 dígitos vira texto; o resto fora do padrão reprova.

    A mensagem de erro sempre traz o valor ofensivo e onde ele está.
    """
    if isinstance(value, bool):
        raise CrosswalkSchemaError(f"código inválido: {value!r} em {where}")
    if isinstance(value, (int, float)):
        if value < 0 or (isinstance(value, float) and not value.is_integer()):
            raise CrosswalkSchemaError(f"código inválido: {value!r} em {where}")
        text = str(int(value))
        if len(text) != 6:
            raise CrosswalkSchemaError(
                f"código numérico com {len(text)} dígitos (zero à esquerda perdido): {value!r} em {where}"
            )
        return text, True
    if isinstance(value, str):
        text = value.strip()
        if CODE.fullmatch(text):
            return text, False
    raise CrosswalkSchemaError(f"código inválido: {value!r} em {where}")


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _read_sheet(dataset: dict[str, Any], path: Path) -> list[tuple]:
    name = dataset["id"]
    sheet_name = dataset.get("sheet")
    if not sheet_name:
        raise CrosswalkSchemaError(f"{name}: o catálogo não declara a aba (sheet)")
    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
    except (InvalidFileException, zipfile.BadZipFile, KeyError, OSError) as exc:
        raise CrosswalkSchemaError(f"{name}: o arquivo não é uma planilha xlsx válida") from exc
    except Exception as exc:
        raise CrosswalkSchemaError(f"{name}: a planilha não pôde ser lida: {exc}") from exc
    try:
        sheets = {normalize_label(sheet): sheet for sheet in workbook.sheetnames}
        if normalize_label(sheet_name) not in sheets:
            raise CrosswalkSchemaError(f"{name}: aba ausente: {sheet_name}")
        return list(workbook[sheets[normalize_label(sheet_name)]].iter_rows(values_only=True))
    except CrosswalkSchemaError:
        raise
    except Exception as exc:
        raise CrosswalkSchemaError(f"{name}: a planilha não pôde ser lida: {exc}") from exc
    finally:
        workbook.close()


def load_rows(dataset: dict[str, Any], path: Path) -> tuple[list[dict[str, str]], dict[str, int]]:
    """Linhas de dado da planilha, com as colunas do catálogo (``dataset["columns"]``) como chaves.

    Códigos já normalizados (`pre_code` e `code`), designações limpas. Estatísticas: ``rows_read`` (linhas com
    conteúdo, incluindo legendas), ``ignored_rows`` (legendas), ``numeric_codes_normalized`` (células) e
    ``partial_rows`` (linhas cuja designação pré-2013 termina em "(parte)").
    """
    name = dataset["id"]
    columns: dict[str, str] = dataset.get("columns") or {}
    if not columns:
        raise CrosswalkSchemaError(f"{name}: o catálogo não declara as colunas (columns)")
    rows = _read_sheet(dataset, Path(path))
    if not rows:
        raise CrosswalkSchemaError(f"{name}: planilha vazia")

    index: dict[str, int] = {}
    for position, label in enumerate(rows[0]):
        index.setdefault(normalize_label(label), position)
    position_of: dict[str, int] = {}
    for role, label in columns.items():
        if normalize_label(label) not in index:
            raise CrosswalkSchemaError(f"{name}: coluna ausente: {label}")
        position_of[role] = index[normalize_label(label)]

    result: list[dict[str, str]] = []
    ignored = numeric = partial = 0
    for number, row in enumerate(rows[1:], start=2):
        cells = {role: (row[pos] if pos < len(row) else None) for role, pos in position_of.items()}
        if all(_blank(value) for value in cells.values()):
            continue  # linha vazia: pulada sem contar
        first = cells.get("pre_code")
        others_blank = all(_blank(value) for role, value in cells.items() if role != "pre_code")
        if others_blank and isinstance(first, str) and not CODE.fullmatch(first.strip()):
            ignored += 1  # legenda ou rodapé: texto na primeira coluna e nada nas outras
            continue
        record: dict[str, str] = {}
        for role, value in cells.items():
            if role in ("pre_code", "code"):
                code, was_numeric = normalize_code(value, where=f"{name} linha {number} coluna {role}")
                numeric += was_numeric
                record[role] = code
            else:
                record[role] = normalize_text(value)
        partial += is_partial(record.get("pre_name", ""))
        result.append(record)
    stats = {
        "rows_read": len(result) + ignored,
        "ignored_rows": ignored,
        "numeric_codes_normalized": numeric,
        "partial_rows": partial,
    }
    return result, stats
