"""Leitura das planilhas do INE (`layout.py`): códigos, rótulos, legendas e planilhas inválidas (spec 004, T004)."""

import unicodedata

import pytest
from openpyxl import Workbook

from pipelines.collectors.parish_crosswalk.layout import (
    CrosswalkSchemaError,
    is_partial,
    load_rows,
    normalize_code,
    normalize_label,
)
from tests.fixtures.parish_crosswalk.tables import (
    LABELS_A,
    LABELS_B,
    ROWS_A,
    SHEET_A,
    dataset,
    make_table_a,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("010103", ("010103", False)),
        ("  010103 ", ("010103", False)),
        ("0308FC", ("0308FC", False)),
        (110640, ("110640", True)),
        (110640.0, ("110640", True)),
    ],
)
def test_normalize_code_accepts_text_and_whole_six_digit_numbers(value, expected):
    assert normalize_code(value, where="t") == expected


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (10103, "5 dígitos"),            # zero à esquerda perdido
        (1234567, "7 dígitos"),
        (110640.5, "110640.5"),
        (-110640, "-110640"),
        (True, "True"),
        (None, "None"),
        ("", "''"),
        ("0308fc", "0308fc"),            # minúscula
        ("01 0103", "01 0103"),          # espaço interno
        ("0101030", "0101030"),          # 7 caracteres
        ("ZZ", "ZZ"),
    ],
)
def test_normalize_code_rejects_everything_else_and_names_the_offending_value(value, message):
    with pytest.raises(CrosswalkSchemaError, match=message):
        normalize_code(value, where="tabela linha 2")


def test_labels_are_compared_without_case_extra_spaces_or_unicode_form():
    decomposed = unicodedata.normalize("NFD", "Código -  Freguesias repostas em 2025")
    assert normalize_label(decomposed) == normalize_label("código - freguesias repostas em 2025 ")
    assert normalize_label(None) == ""


def test_is_partial_only_matches_the_marker_at_the_end():
    assert is_partial("Bicos (parte)") and is_partial("Bicos (PARTE)  ")
    assert not is_partial("Parte Alta") and not is_partial("Bicos (parte) Norte")


def _workbook(path, header, rows, *, sheet="Plan", width=None):
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet
    worksheet.append(list(header) + [None] * ((width or len(header)) - len(header)))
    for row in rows:
        worksheet.append(list(row))
    workbook.save(path)
    return path


def test_header_with_extra_spaces_matches_the_catalog_and_columns_are_found_by_label_not_position(tmp_path):
    spec = {**dataset("reposicao_2025"), "columns": {**LABELS_B, "code": "Código - Freguesias repostas em 2025"}}
    shuffled = [LABELS_B["name"], LABELS_B["code"], LABELS_B["municipality_name"], LABELS_B["pre_name"],
                LABELS_B["pre_code"]]  # ordem invertida e o código com dois espaços
    path = _workbook(tmp_path / "b.xlsx", shuffled, [("Agadão", "010128", "Águeda", "Agadão", "010101")], sheet="Sheet1")
    rows, _ = load_rows(spec, path)
    assert rows == [{"pre_code": "010101", "pre_name": "Agadão", "municipality_name": "Águeda",
                     "code": "010128", "name": "Agadão"}]


def test_extra_empty_columns_and_blank_rows_are_skipped_without_counting(tmp_path):
    header = [LABELS_A["pre_code"], LABELS_A["pre_name"], LABELS_A["name"], LABELS_A["code"]]
    rows = [("010103", "Aguada de Cima", "Aguada de Cima", "010103")]
    path = _workbook(tmp_path / "a.xlsx", header, [*rows, (None,) * 40, ("", "  ", None, None), *rows], sheet=SHEET_A,
                     width=40)
    loaded, stats = load_rows(dataset("reorganizacao_2013"), path)
    assert len(loaded) == 2 and stats == {
        "rows_read": 2, "ignored_rows": 0, "numeric_codes_normalized": 0, "partial_rows": 0,
    }


def test_legend_is_ignored_and_counted_but_text_with_data_in_other_columns_is_an_invalid_row(tmp_path):
    ok = make_table_a(tmp_path / "ok.xlsx", extra=[("Fonte: INE, 2013", None, None, None), ("Nota", "", " ", None)])
    loaded, stats = load_rows(dataset("reorganizacao_2013"), ok)
    assert len(loaded) == len(ROWS_A) and stats["ignored_rows"] == 2 and stats["rows_read"] == len(ROWS_A) + 2
    bad = make_table_a(tmp_path / "bad.xlsx", extra=[("Nota", "texto", None, None)])
    with pytest.raises(CrosswalkSchemaError, match="Nota"):
        load_rows(dataset("reorganizacao_2013"), bad)


def test_a_row_with_code_but_without_destination_code_is_invalid(tmp_path):
    path = make_table_a(tmp_path / "x.xlsx", [("010103", "Aguada de Cima", "Aguada de Cima", None)])
    with pytest.raises(CrosswalkSchemaError, match="linha 2 coluna code"):
        load_rows(dataset("reorganizacao_2013"), path)


def test_numeric_cells_are_counted_per_cell_and_partial_rows_per_row(tmp_path):
    path = make_table_a(tmp_path / "a.xlsx")
    loaded, stats = load_rows(dataset("reorganizacao_2013"), path)
    belem = next(row for row in loaded if row["pre_name"] == "São Francisco Xavier")
    assert (belem["pre_code"], belem["code"]) == ("110640", "110658")
    assert stats["numeric_codes_normalized"] == 2 and stats["partial_rows"] == 3


@pytest.mark.parametrize("case", ["sheet", "column", "not_xlsx", "html", "empty_file", "empty_sheet", "no_sheet_in_catalog"])
def test_invalid_workbooks_are_rejected_with_the_reason(tmp_path, case):
    spec = dataset("reorganizacao_2013")
    path = tmp_path / "a.xlsx"
    if case == "sheet":
        make_table_a(path, sheet="Plan1")
        message = "aba ausente"
    elif case == "column":
        make_table_a(path, labels={**LABELS_A, "code": "Outra"})
        message = "coluna ausente: Código Novo"
    elif case == "not_xlsx":
        path.write_bytes(b"a,b\n1,2\n")
        message = "não é uma planilha"
    elif case == "html":
        path.write_bytes(b"<html><body>erro</body></html>")
        message = "não é uma planilha"
    elif case == "empty_file":
        path.write_bytes(b"")
        message = "não é uma planilha"
    elif case == "empty_sheet":
        workbook = Workbook()
        workbook.active.title = SHEET_A
        workbook.save(path)
        message = "planilha vazia"
    else:
        make_table_a(path)
        spec = {k: v for k, v in spec.items() if k != "sheet"}
        message = "não declara a aba"
    with pytest.raises(CrosswalkSchemaError, match=message):
        load_rows(spec, path)


def test_missing_columns_mapping_in_the_catalog_is_rejected(tmp_path):
    path = make_table_a(tmp_path / "a.xlsx")
    with pytest.raises(CrosswalkSchemaError, match="não declara as colunas"):
        load_rows({k: v for k, v in dataset("reorganizacao_2013").items() if k != "columns"}, path)
