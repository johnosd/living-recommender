"""Casos de borda do gate de cobertura (spec 004, T019); o essencial está no contrato."""

import numpy as np
import pandas as pd
import pytest

from pipelines.collectors.parish_crosswalk.coverage import (
    MAX_LISTED,
    CrosswalkCoverageError,
    verify_coverage,
)


def _crosswalk(*pairs):
    return pd.DataFrame(pairs, columns=["dicofre_2013", "dicofre_2025"])


@pytest.mark.parametrize("container", [set, list, tuple, pd.Series, np.array])
def test_the_dimension_and_the_2013_codes_can_be_any_collection(container):
    crosswalk = _crosswalk(("010103", "010103"), ("010123", "010128"))
    verify_coverage(crosswalk, container(["010103", "010128"]), container(["010103", "010123"]))


def test_duplicated_pairs_and_extra_columns_do_not_matter():
    crosswalk = _crosswalk(("010103", "010103"), ("010103", "010103")).assign(relation="one_to_one")
    verify_coverage(crosswalk, {"010103"}, {"010103"})


def test_each_kind_alone_leaves_the_other_lists_empty_and_the_message_names_only_that_kind():
    crosswalk = _crosswalk(("010103", "010103"))
    with pytest.raises(CrosswalkCoverageError) as error:
        verify_coverage(crosswalk, {"010103", "999999"}, {"010103"})
    err = error.value
    assert err.parishes_without_origin == ["999999"]
    assert err.codes_2013_without_destination == [] and err.unknown_destinations == []
    text = str(err)
    assert text.startswith("cobertura reprovada") and "sem origem (1): 999999" in text
    assert "sem destino" not in text and "fora da dim_parish" not in text
    assert isinstance(err, ValueError)


def test_lists_are_sorted_and_counted_and_names_only_enrich_parishes_without_origin():
    crosswalk = _crosswalk(("010103", "010103"))
    dim = {"010103", "999998", "999997"}
    with pytest.raises(CrosswalkCoverageError) as error:
        verify_coverage(crosswalk, dim, {"010103", "010199", "010198"},
                        names={"999997": "Vila Nova", "999998": "Vila Velha", "010199": "não deve aparecer"})
    err = error.value
    assert err.parishes_without_origin == ["999997", "999998"]
    assert err.codes_2013_without_destination == ["010198", "010199"]
    text = str(err)
    assert "(2): 999997 Vila Nova, 999998 Vila Velha" in text
    assert "(2): 010198, 010199" in text and "não deve aparecer" not in text


def test_a_long_gap_is_fully_in_the_attribute_but_truncated_in_the_message():
    crosswalk = _crosswalk(("010103", "010103"))
    missing = {f"9{number:05d}" for number in range(MAX_LISTED + 10)}
    with pytest.raises(CrosswalkCoverageError) as error:
        verify_coverage(crosswalk, {"010103"} | missing, {"010103"})
    err = error.value
    assert len(err.parishes_without_origin) == MAX_LISTED + 10
    assert f"({MAX_LISTED + 10})" in str(err) and "e mais 10" in str(err)
    assert str(err).count("900") <= MAX_LISTED + 1


def test_an_empty_crosswalk_reports_everything_as_missing():
    crosswalk = _crosswalk()
    with pytest.raises(CrosswalkCoverageError) as error:
        verify_coverage(crosswalk, {"010103"}, {"010103"})
    assert error.value.parishes_without_origin == ["010103"]
    assert error.value.codes_2013_without_destination == ["010103"]
