"""Relatório de cobertura por dataset: contagens, ausentes por nome e ausência nunca imputada (US4)."""

import pandas as pd
import pytest

from pipelines.cli import build_observations as builder
from tests.fixtures.observations.ci_seed import seed

STAGING = "lake/bronze/stg_observation/data.parquet"


def _build(tmp_path, **options):
    root = tmp_path / "data"
    seed(root, prepare=False, **options)
    result = builder.build_observations(root)
    coverage = result["coverage"].set_index(["source_id", "dataset_id"])
    return root, result, coverage


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """Um único build (dbt incluído) compartilhado pelos testes que só leem o resultado."""
    return _build(tmp_path_factory.mktemp("coverage"))


def test_coverage_counts_and_lists_the_municipalities_without_value(built):
    _, _, coverage = built
    assert len(coverage) == 20
    rendas = coverage.loc[("ine", "rendas_novos_contratos")]
    assert rendas.latest_period == 2025 and rendas.latest_period_with_data == 2025
    assert (rendas.municipalities_expected, rendas.municipalities_with_value) == (308, 298)
    assert rendas.municipalities_without_value == 10
    assert sorted(rendas.missing_dico) == [f"{number:04d}" for number in range(1, 11)]
    assert rendas.aggregate_rows_excluded == 0

    first = coverage.loc[("pordata", "populacao_residente_sexo_idade")]  # `x` no 1.º município, último ano
    assert (first.municipalities_with_value, first.municipalities_without_value) == (307, 1)
    assert list(first.missing_dico) == ["0001"] and first.aggregate_rows_excluded == 1  # a linha "Portugal"
    full = coverage.loc[("pordata", "densidade_populacional")]
    assert full.municipalities_with_value == 308 and len(full.missing_dico) == 0
    assert full.aggregate_rows_excluded == 2  # "Portugal" e a linha de país do layout com `Nome País`


def test_absence_stays_null_with_its_symbol_in_the_staging(built):
    root, _, _ = built
    staging = pd.read_parquet(root / STAGING)
    row = staging[(staging.dataset_id == "populacao_residente_sexo_idade") & (staging.dico == "0001")
                  & (staging.period == 2024)].iloc[0]
    assert pd.isna(row.value) and row.symbol == "x"
    assert (staging.value.isna() & staging.symbol.isna()).sum() == 0
    assert (staging.value == 0).sum() == 0  # nada foi convertido em zero


def test_coverage_csv_lists_each_missing_municipality_with_code_and_name(built):
    root, _, _ = built
    report = pd.read_csv(root / "lake/bronze/coverage.csv", sep=";", encoding="utf-8-sig", dtype=str)
    assert len(report) == 20 and "missing_dico" not in report.columns
    rendas = report[report.dataset_id == "rendas_novos_contratos"].iloc[0]
    assert rendas.municipalities_with_value == "298"
    assert rendas.missing.startswith("0001 Município 0001; 0002 Município 0002")
    complete = report[report.dataset_id == "densidade_populacional"].iloc[0]
    assert pd.isna(complete.missing)


def test_a_dataset_with_nothing_in_the_latest_period_reports_zero_and_the_last_period_with_data(tmp_path):
    _, _, coverage = _build(tmp_path, rendas_latest_empty=True)
    rendas = coverage.loc[("ine", "rendas_novos_contratos")]
    assert rendas.latest_period == 2025 and rendas.latest_period_with_data == 2024
    assert rendas.municipalities_with_value == 0 and rendas.municipalities_without_value == 308
    assert len(rendas.missing_dico) == 308


def test_the_console_table_names_the_datasets_and_the_ones_not_collected(built):
    _, result, _ = built
    text = builder.format_coverage(result["coverage"], result["not_collected"])
    assert "ine/rendas_novos_contratos" in text and "298/308" in text and "sem sem valor" not in text
    assert "não coletados: pordata/poder_compra_per_capita_xlsx" in text
