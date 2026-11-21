"""Não inferir equivalência territorial nem revelar valores suprimidos."""

import pandas as pd
import pytest

from pipelines.collectors.censos2021.territory import align_censos
from tests.fixtures.censos2021.responses import territory_frames


def test_partial_one_to_one_is_missing_and_conflict_rejected():
    obs, dim, xwalk, cats = territory_frames()
    xwalk.loc[xwalk.dicofre_2025 == "0308FD", ["relation", "partial_origin"]] = [
        "one_to_one",
        True,
    ]
    out = align_censos(obs, dim, xwalk, categories=cats, target_version="2025")
    assert out[out.dicofre == "0308FD"].coverage_status.eq("missing").all()
    bad = pd.concat([obs, obs.iloc[:1].assign(value=999)])
    with pytest.raises(ValueError):
        align_censos(bad, dim, xwalk, categories=cats, target_version="2025")


def test_suppressed_direct_does_not_fall_back_to_union_and_orphans_are_audited():
    obs, dim, xwalk, cats = territory_frames()
    obs.loc[obs.source_dicofre == "0308FC", ["value", "value_status"]] = [
        None,
        "suppressed",
    ]
    obs = pd.concat([obs, obs.iloc[:1].assign(source_dicofre="010199")])
    out = align_censos(obs, dim, xwalk, categories=cats, target_version="2025")
    assert out[out.dicofre == "0308FC"].value.isna().all()
    assert out[out.dicofre == "0308FC"].reason.eq("official_suppression").all()
    assert out.attrs["orphans"][0]["source_dicofre"] == "010199"


def test_explicit_official_not_published_can_use_fallback():
    obs, dim, xwalk, cats = territory_frames()
    obs.loc[obs.source_dicofre == "0308FC", ["value", "value_status"]] = [
        None,
        "not_published",
    ]
    out = align_censos(obs, dim, xwalk, categories=cats, target_version="2025")
    assert out[out.dicofre == "0308FC"].coverage_status.eq("inherited").all()


def test_official_absence_is_preserved_when_no_fallback_solution_exists():
    obs, dim, xwalk, cats = territory_frames()
    obs.loc[obs.source_dicofre == "010103", ["value", "value_status"]] = [
        None,
        "not_published",
    ]
    xwalk = xwalk[xwalk.dicofre_2025 != "010103"]
    out = align_censos(obs, dim, xwalk, categories=cats, target_version="2025")
    assert out[out.dicofre == "010103"].reason.eq("official_not_published").all()
    assert out[out.dicofre == "010103"].value.isna().all()
