"""Validação e leitura da planilha manual do Pordata (layout hierárquico)."""

import pandas as pd
import pytest

from pipelines.collectors._shared.catalog import get_dataset_source, load_catalog
from pipelines.collectors.pordata.transform import read_pordata_xlsx
from pipelines.collectors.pordata.validate import PordataSchemaError
from pipelines.collectors.pordata.xlsx import validate_pordata_xlsx
from tests.fixtures.pordata.xlsx import make_pordata_xlsx

DATASET = next(d for d in get_dataset_source(load_catalog(), "pordata")["datasets"]
               if d["id"] == "poder_compra_per_capita_xlsx")
NAMES = [f"Município {number:03d}" for number in range(308)]


def test_a_valid_workbook_passes_and_reads_one_observation_per_municipality_and_year(tmp_path):
    path = make_pordata_xlsx(tmp_path / "p.xlsx", NAMES)
    validate_pordata_xlsx(DATASET, path)
    frame, excluded = read_pordata_xlsx(DATASET, path)
    assert len(frame) == 308 * 2 and excluded == 4  # as 4 linhas NUTS; a legenda do rodapé não conta
    assert frame.period.tolist()[:2] == [2019, 2021] and frame.period.dtype == "int64"
    assert set(frame.unit) == {"Número índice (Portugal = 100)"} and frame.value.notna().all()
    assert frame.iloc[0].to_dict() | {"value": 0} == {
        "source_name": "Município 000", "period": 2019, "filter_1": "", "filter_2": "", "filter_3": "",
        "value": 0, "symbol": None, "unit": "Número índice (Portugal = 100)",
    }


def test_empty_cells_and_text_symbols_become_null_with_a_symbol_never_zero(tmp_path):
    path = make_pordata_xlsx(tmp_path / "p.xlsx", NAMES,
                             missing={("Município 001", 2021): None, ("Município 002", 2019): "x"})
    frame, _ = read_pordata_xlsx(DATASET, path)
    empty = frame[(frame.source_name == "Município 001") & (frame.period == 2021)].iloc[0]
    text = frame[(frame.source_name == "Município 002") & (frame.period == 2019)].iloc[0]
    assert pd.isna(empty.value) and empty.symbol == "vazio"
    assert pd.isna(text.value) and text.symbol == "x"
    assert (frame.value == 0).sum() == 0


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"sheets": ("Quadro",)}, "aba ausente: Metainformação"),
        ({"sheets": ("Metainformação",)}, "aba ausente: Quadro"),
        ({"with_header": False}, "cabeçalho"),
    ],
)
def test_workbooks_with_a_missing_sheet_or_header_are_rejected(tmp_path, options, message):
    path = make_pordata_xlsx(tmp_path / "p.xlsx", NAMES, **options)
    with pytest.raises(PordataSchemaError, match=message):
        validate_pordata_xlsx(DATASET, path)


def test_a_workbook_without_all_308_municipalities_is_rejected(tmp_path):
    path = make_pordata_xlsx(tmp_path / "p.xlsx", NAMES[:307])
    with pytest.raises(PordataSchemaError, match="307 linhas 'Município' no lugar de 308"):
        validate_pordata_xlsx(DATASET, path)


def test_a_file_that_is_not_a_workbook_is_rejected(tmp_path):
    path = tmp_path / "falso.xlsx"
    path.write_text("isto não é uma planilha", encoding="utf-8")
    with pytest.raises(PordataSchemaError, match="planilha xlsx válida"):
        validate_pordata_xlsx(DATASET, path)
