"""Planilha de poder de compra do Pordata, exportada à mão (layout hierárquico).

Layout observado na exportação real (2026-11-11): abas `Quadro`, `Metainformação` e `Alterações NUTS`;
na `Quadro`, uma linha de cabeçalho `Âmbito Geográfico | Anos | <ano> | <ano> ...`, depois linhas
`<âmbito> | <território> | <valor por ano>`, com o âmbito `NUTS 2013`/`NUTS I`/`NUTS II`/`NUTS III`
para as agregações e `Município` para os 308 municípios, e uma legenda de símbolos no rodapé.
"""

import unicodedata
import zipfile
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from pipelines.collectors.pordata.validate import (
    MUNICIPALITY_SCOPE,
    SCOPE_LABEL,
    PordataSchemaError,
)

REQUIRED_SHEETS = ("Quadro", "Metainformação")
DATA_SHEET = "Quadro"
YEARS_LABEL = "Anos"
EXPECTED_MUNICIPALITIES = 308
HEADER_SEARCH_ROWS = 60
EMPTY_SYMBOL = "vazio"


def _norm(value: Any) -> str:
    return unicodedata.normalize("NFC", str(value)).strip().casefold() if value is not None else ""


def parse_pordata_xlsx(dataset: dict[str, Any], path: Path) -> tuple[list[int], list[tuple[str, str, list[Any]]]]:
    """Devolve ``(anos, linhas)``, com cada linha ``(âmbito, território, valores por ano)``.

    Reprova arquivo que não é planilha, abas ausentes, cabeçalho de anos ausente e contagem de
    municípios diferente de 308. Só lê; o arquivo do operador nunca é alterado.
    """
    name = dataset["id"]
    try:
        workbook = load_workbook(path, read_only=True, data_only=True)
    except (InvalidFileException, zipfile.BadZipFile, KeyError, OSError) as exc:
        raise PordataSchemaError(f"{name}: o arquivo não é uma planilha xlsx válida") from exc
    try:
        sheets = {_norm(sheet): sheet for sheet in workbook.sheetnames}
        missing = [sheet for sheet in REQUIRED_SHEETS if _norm(sheet) not in sheets]
        if missing:
            raise PordataSchemaError(f"{name}: aba ausente: {', '.join(missing)}")
        rows = list(workbook[sheets[_norm(DATA_SHEET)]].iter_rows(values_only=True))
    finally:
        workbook.close()

    header = next(
        (index for index, row in enumerate(rows[:HEADER_SEARCH_ROWS])
         if len(row) > 2 and _norm(row[0]) == _norm(SCOPE_LABEL) and _norm(row[1]) == _norm(YEARS_LABEL)),
        None,
    )
    if header is None:
        raise PordataSchemaError(f"{name}: cabeçalho '{SCOPE_LABEL} | {YEARS_LABEL}' ausente na aba {DATA_SHEET}")
    years: list[int] = []
    for cell in rows[header][2:]:
        if cell is None or str(cell).strip() == "":
            break
        try:
            years.append(int(float(str(cell))))
        except ValueError as exc:
            raise PordataSchemaError(f"{name}: ano inválido no cabeçalho: {cell!r}") from exc
    if not years:
        raise PordataSchemaError(f"{name}: cabeçalho sem colunas de ano")

    parsed = [
        (str(row[0]).strip(), str(row[1]).strip(), list(row[2:2 + len(years)]))
        for row in rows[header + 1:]
        if len(row) > 1 and row[0] is not None and row[1] is not None
    ]
    municipalities = sum(1 for scope, _, _ in parsed if scope == MUNICIPALITY_SCOPE)
    if municipalities != EXPECTED_MUNICIPALITIES:
        raise PordataSchemaError(
            f"{name}: {municipalities} linhas '{MUNICIPALITY_SCOPE}' no lugar de {EXPECTED_MUNICIPALITIES}"
        )
    return years, parsed


def validate_pordata_xlsx(dataset: dict[str, Any], path: Path) -> None:
    parse_pordata_xlsx(dataset, path)
