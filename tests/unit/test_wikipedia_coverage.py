from copy import deepcopy

import pytest

from pipelines.collectors.wikipedia.coverage import assess_wikipedia_coverage
from tests.fixtures.wikipedia.responses import associations, municipalities


def valid(code):
    return {"dico": code, "status": "valid", "identity_validated": True,
            "revision_id": 42, "extraction_complete": True, "has_introduction": False, "section_count": 1}


def test_wikipedia_short_article_without_intro_or_theme_can_be_complete():
    result = assess_wikipedia_coverage(municipalities(), [valid("0001"), valid("0002")])
    assert result["ready"] and result["counts"] == {"valid": 2}


@pytest.mark.parametrize("case", ["missing", "extra", "duplicate", "failed", "pending", "identity_pending",
    "extraction_failed", "unknown", "old_valid", "bad_revision", "no_absence_review"])
def test_wikipedia_each_gap_is_a_blocker(case):
    entries = [valid("0001"), valid("0002")]
    if case == "missing":
        entries.pop()
    elif case == "extra":
        entries[1]["dico"] = "9999"
    elif case == "duplicate":
        entries.append(deepcopy(entries[0]))
    elif case == "bad_revision":
        entries[0]["revision_id"] = 0
    elif case == "old_valid":
        entries[0].update(status="failed", previous_valid_revision_id=42)
    elif case == "no_absence_review":
        entries[0].update(status="absent", reason="none", absence_evidence={})
    else:
        entries[0]["status"] = case
    result = assess_wikipedia_coverage(municipalities(), entries)
    assert not result["ready"] and result["blockers"]


def test_wikipedia_reviewed_absence_and_invalid_dimension():
    absence = {"dico": "0002", "status": "absent", "reason": "no_appropriate_pt_article",
               "absence_evidence": associations()[1]}
    assert assess_wikipedia_coverage(municipalities(), [valid("0001"), absence])["ready"]
    assert not assess_wikipedia_coverage([], [valid("0001")])["ready"]
    assert not assess_wikipedia_coverage(municipalities(), [valid("0001"), absence], input_errors=("checksum",))["ready"]
