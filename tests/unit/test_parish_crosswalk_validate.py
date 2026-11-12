"""Validação das planilhas do INE antes de virarem bruto (spec 004, FR-005)."""

import zipfile

import pytest
from openpyxl import Workbook

from pipelines.collectors._shared.catalog import get_dataset_source, load_catalog
from pipelines.collectors.parish_crosswalk.layout import normalize_label
from pipelines.collectors.parish_crosswalk.validate import (
    CrosswalkSchemaError,
    validate_crosswalk_table,
)
from tests.fixtures.parish_crosswalk.tables import (
    LABELS_A,
    LABELS_B,
    SHEET_A,
    dataset,
    make_table_a,
    make_table_b,
)


def test_both_real_layouts_pass(tmp_path):
    validate_crosswalk_table(dataset("reorganizacao_2013"), make_table_a(tmp_path / "a.xlsx"))
    validate_crosswalk_table(dataset("reposicao_2025"), make_table_b(tmp_path / "b.xlsx"))


def test_a_workbook_with_only_the_header_has_no_data_rows(tmp_path):
    path = make_table_a(tmp_path / "a.xlsx", [])
    with pytest.raises(CrosswalkSchemaError, match="reorganizacao_2013: nenhuma linha de dado"):
        validate_crosswalk_table(dataset("reorganizacao_2013"), path)


def test_a_workbook_with_only_legends_has_no_data_rows(tmp_path):
    path = make_table_a(tmp_path / "a.xlsx", [("Fonte: INE", None, None, None)])
    with pytest.raises(CrosswalkSchemaError, match="nenhuma linha de dado"):
        validate_crosswalk_table(dataset("reorganizacao_2013"), path)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"", "não é uma planilha"),
        (b"<html><body>Pagina nao encontrada</body></html>", "não é uma planilha"),
        (b"a,b\n1,2\n", "não é uma planilha"),
    ],
)
def test_files_that_are_not_workbooks_name_the_dataset(tmp_path, content, message):
    path = tmp_path / "x.xlsx"
    path.write_bytes(content)
    with pytest.raises(CrosswalkSchemaError, match=f"reposicao_2025: .*{message}"):
        validate_crosswalk_table(dataset("reposicao_2025"), path)


def test_a_zip_that_is_not_a_workbook_is_rejected(tmp_path):
    path = tmp_path / "x.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("qualquer.txt", "nada")
    with pytest.raises(CrosswalkSchemaError, match="não é uma planilha"):
        validate_crosswalk_table(dataset("reorganizacao_2013"), path)


def test_a_workbook_with_broken_xml_is_rejected_instead_of_crashing(tmp_path):
    good = make_table_a(tmp_path / "good.xlsx")
    broken = tmp_path / "broken.xlsx"
    with zipfile.ZipFile(good) as source, zipfile.ZipFile(broken, "w") as target:
        for item in source.infolist():
            data = source.read(item.filename)
            target.writestr(item.filename, b"<broken" if item.filename.startswith("xl/worksheets/") else data)
    with pytest.raises(CrosswalkSchemaError):
        validate_crosswalk_table(dataset("reorganizacao_2013"), broken)


def test_missing_sheet_and_missing_column_are_named(tmp_path):
    with pytest.raises(CrosswalkSchemaError, match="aba ausente: Correspondências 2013"):
        validate_crosswalk_table(dataset("reorganizacao_2013"), make_table_a(tmp_path / "a.xlsx", sheet="Plan1"))
    wrong = make_table_b(tmp_path / "b.xlsx", labels={**LABELS_B, "municipality_name": "Município"})
    with pytest.raises(CrosswalkSchemaError, match="coluna ausente: Designação - Município"):
        validate_crosswalk_table(dataset("reposicao_2025"), wrong)


def test_an_empty_workbook_and_an_invalid_code_are_rejected(tmp_path):
    empty = tmp_path / "empty.xlsx"
    workbook = Workbook()
    workbook.active.title = SHEET_A
    workbook.save(empty)
    with pytest.raises(CrosswalkSchemaError, match="planilha vazia"):
        validate_crosswalk_table(dataset("reorganizacao_2013"), empty)
    bad = make_table_a(tmp_path / "bad.xlsx", [("010103", "X", "X", "01010"), ("010104", "Y", "Y", "010104")])
    with pytest.raises(CrosswalkSchemaError, match="01010"):
        validate_crosswalk_table(dataset("reorganizacao_2013"), bad)


def test_the_real_catalog_labels_match_the_layout_the_fixtures_reproduce():
    real = {d["id"]: d for d in get_dataset_source(load_catalog(), "ine_parish_crosswalk")["datasets"]}
    for dataset_id, labels in (("reorganizacao_2013", LABELS_A), ("reposicao_2025", LABELS_B)):
        assert {r: normalize_label(v) for r, v in real[dataset_id]["columns"].items()} == {
            r: normalize_label(v) for r, v in labels.items()
        }
    assert normalize_label(real["reorganizacao_2013"]["sheet"]) == normalize_label(SHEET_A)
