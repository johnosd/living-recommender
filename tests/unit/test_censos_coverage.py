"""Cobertura completa é igualdade de chaves, não uma contagem aproximada."""

import pandas as pd
import pytest

from pipelines.collectors.censos2021.coverage import assess_censos_coverage


@pytest.mark.parametrize(
    "case,blocker",
    [
        ("duplicate", "duplicate_record"),
        ("extra", "unexpected_record"),
        ("missing", "missing_record"),
        ("unexplained", "unexplained_absence"),
    ],
)
def test_coverage_does_not_hide_records_by_equal_counts(case, blocker):
    dim = pd.DataFrame({"dicofre": ["010101"]})
    cats = pd.DataFrame({"age_code": ["T", "25_29"]})
    data = pd.DataFrame(
        {
            "dicofre": ["010101"] * 2,
            "age_code": ["T", "25_29"],
            "coverage_status": ["own", "missing"],
            "value": [10, None],
            "reason": [None, "official_suppression"],
        }
    )
    assert assess_censos_coverage(data, dim, cats)["ready"]
    if case == "duplicate":
        data = pd.concat([data, data.iloc[:1]])
    if case == "extra":
        data.loc[0, "dicofre"] = "999999"
    if case == "missing":
        data = data.iloc[:1]
    if case == "unexplained":
        data.loc[1, "reason"] = None
    assert blocker in assess_censos_coverage(data, dim, cats)["blockers"]
