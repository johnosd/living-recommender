"""Validação do CSV do Pordata pelo rótulo, nos três layouts reais."""

import pytest

from pipelines.collectors._shared.catalog import get_dataset_source, load_catalog
from pipelines.collectors.pordata.validate import (
    PordataSchemaError,
    clean_label,
    validate_pordata_csv,
)
from tests.fixtures.pordata.layouts import pordata_csv

DATASET = get_dataset_source(load_catalog(), "pordata")["datasets"][0]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("01. Ano", "Ano"), ("08. Escala ", "Escala"), ("Max. 08. Escala ", "Escala"),
     ("04. Âmbito Geográfico", "Âmbito Geográfico"), ("Valor", "Valor")],
)
def test_clean_label_drops_numeric_prefix_and_spaces(raw, expected):
    assert clean_label(raw) == expected


@pytest.mark.parametrize("layout", ["a", "b", "c"])
def test_all_three_real_layouts_pass(tmp_path, layout):
    path = tmp_path / "d.csv"
    path.write_text(pordata_csv(layout), encoding="utf-8", newline="")
    validate_pordata_csv(DATASET, path)


def _write(tmp_path, text):
    path = tmp_path / "d.csv"
    path.write_text(text, encoding="utf-8", newline="")
    return path


def test_missing_label_is_named_in_the_message(tmp_path):
    text = pordata_csv("a").replace("09. Valor", "09. Quantidade")
    with pytest.raises(PordataSchemaError, match="coluna ausente: Valor"):
        validate_pordata_csv(DATASET, _write(tmp_path, text))


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "vazio"),
        ("<html><body>erro</body></html>", "HTML"),
        (pordata_csv("a", municipalities=()), "nenhuma linha"),
    ],
)
def test_empty_html_and_files_without_municipal_rows_are_rejected(tmp_path, text, message):
    with pytest.raises(PordataSchemaError, match=message):
        validate_pordata_csv(DATASET, _write(tmp_path, text))


def test_non_utf8_file_is_rejected(tmp_path):
    path = tmp_path / "d.csv"
    path.write_bytes("01. Ano,Município\n".encode("latin-1") + b"\xff\xfe")
    with pytest.raises(PordataSchemaError, match="UTF-8"):
        validate_pordata_csv(DATASET, path)
