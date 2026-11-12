"""Casos de borda da derivação da correspondência 2013→2025 (spec 004, T013); o essencial está no contrato."""

import unicodedata

import pandas as pd
import pytest

from pipelines.collectors.parish_crosswalk.derive import (
    CrosswalkDerivationError,
    derive_parish_crosswalk,
)
from tests.fixtures.parish_crosswalk.tables import scenario_frames

A_COLUMNS = ["pre_code", "pre_name", "name_2013", "code_2013", "partial_origin"]
B_COLUMNS = ["pre_code", "pre_name", "municipality_name", "code_2025", "name_2025"]


def _a(*rows):
    return pd.DataFrame(rows, columns=A_COLUMNS)


def _b(*rows):
    return pd.DataFrame(rows, columns=B_COLUMNS)


def test_without_restored_parishes_every_pair_is_one_to_one_and_keeps_the_2013_code_and_name():
    table_a, _ = scenario_frames()
    frame = derive_parish_crosswalk(table_a, _b())
    assert (frame["dicofre_2013"] == frame["dicofre_2025"]).all()
    assert (frame["name_2013"] == frame["name_2025"]).all()
    assert not frame["name_changed"].any() and not frame["municipality_changed"].any()
    # sem a B, o par muitos-para-um do cenário (090101/090102) continua dois pares independentes
    assert set(frame["relation"]) == {"one_to_one"} and not frame["inherited"].any()


def test_the_inputs_are_not_modified():
    table_a, table_b = scenario_frames()
    before_a, before_b = table_a.copy(), table_b.copy()
    derive_parish_crosswalk(table_a, table_b)
    pd.testing.assert_frame_equal(table_a, before_a)
    pd.testing.assert_frame_equal(table_b, before_b)


def test_a_duplicated_pre2013_code_in_a_keeps_one_pair_per_2013_code():
    table_a = _a(("021113", "Bicos (parte)", "Colos", "021118", True), ("021113", "Bicos (parte)", "Vale", "021122", True))
    frame = derive_parish_crosswalk(table_a, _b())
    assert frame[["dicofre_2013", "dicofre_2025"]].values.tolist() == [["021118", "021118"], ["021122", "021122"]]
    assert frame["partial_origin"].all() and frame["pre2013_codes"].map(list).tolist() == [["021113"], ["021113"]]


def test_the_name_comparison_ignores_case_spaces_and_unicode_form():
    table_a = _a(("010101", "X", "São  João", "010101", False))
    table_b = _b(("010101", "X", "M", "010150", unicodedata.normalize("NFD", "são joão")))
    assert not derive_parish_crosswalk(table_a, table_b)["name_changed"].iloc[0]
    table_b = _b(("010101", "X", "M", "010150", "São Pedro"))
    assert derive_parish_crosswalk(table_a, table_b)["name_changed"].iloc[0]


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("b_unknown", "010999"),
        ("b_repeated", "010101"),
        ("two_names_for_a_2013_code", "código de 2013 com mais de uma designação: 010123"),
        ("two_names_for_a_pair", "par"),
        ("empty_a", "tabela A sem linhas"),
        ("missing_column_a", "tabela A sem colunas: partial_origin"),
        ("missing_column_b", "tabela B sem colunas: name_2025"),
    ],
)
def test_inconsistent_tables_are_rejected_with_the_reason(case, message):
    table_a = _a(("010101", "A", "União", "010123", False), ("010102", "B", "União", "010123", False))
    table_b = _b(("010101", "A", "M", "010128", "A"))
    if case == "b_unknown":
        table_b = _b(("010999", "Z", "M", "010998", "Z"))
    elif case == "b_repeated":
        table_b = _b(("010101", "A", "M", "010128", "A"), ("010101", "A", "M", "010129", "A"))
    elif case == "two_names_for_a_2013_code":
        table_a = _a(("010101", "A", "União 1", "010123", False), ("010102", "B", "União 2", "010123", False))
    elif case == "two_names_for_a_pair":
        table_b = _b(("010101", "A", "M", "010128", "Nome 1"), ("010102", "B", "M", "010128", "Nome 2"))
    elif case == "empty_a":
        table_a = _a()
    elif case == "missing_column_a":
        table_a = table_a.drop(columns="partial_origin")
    else:
        table_b = table_b.drop(columns="name_2025")
    with pytest.raises(CrosswalkDerivationError, match=message):
        derive_parish_crosswalk(table_a, table_b)
