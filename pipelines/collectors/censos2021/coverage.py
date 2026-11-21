"""Avaliação pública de prontidão."""

import json
from collections.abc import Sequence
from pathlib import Path

import pandas as pd


def assess_censos_coverage(
    prepared: pd.DataFrame,
    parishes: pd.DataFrame,
    categories: pd.DataFrame,
    *,
    input_errors: Sequence[str] = (),
) -> dict:
    """Resultado ready, blockers, contagens por coverage_status; não soma habitantes."""
    expected = {(code, age) for code in parishes.dicofre for age in categories.age_code}
    actual = set(zip(prepared.dicofre, prepared.age_code, strict=True))
    blockers = list(input_errors)
    if expected - actual:
        blockers.append("missing_record")
    if actual - expected:
        blockers.append("unexpected_record")
    if prepared.duplicated(["dicofre", "age_code"]).any():
        blockers.append("duplicate_record")
    accepted = {
        "territorial_ambiguity",
        "official_suppression",
        "official_not_applicable",
        "official_not_published",
    }
    missing = prepared.coverage_status.eq("missing")
    if (~prepared.loc[missing, "reason"].isin(accepted)).any():
        blockers.append("unexplained_absence")
    if not prepared.coverage_status.isin(["own", "inherited", "missing"]).all():
        blockers.append("invalid_status")
    if (
        prepared.loc[~missing, "value"].isna().any()
        or prepared.loc[missing, "value"].notna().any()
    ):
        blockers.append("invalid_value_status")
    counts = {
        state: int(prepared.coverage_status.eq(state).sum())
        for state in ("own", "inherited", "missing")
    }
    return {
        "ready": not blockers,
        "blockers": sorted(set(blockers)),
        "expected_observations": len(expected),
        "counts": counts,
    }


def write_censos_reports(summary, candidate: Path):
    """Relatórios só no candidato; resumos contam observações, nunca habitantes herdados."""
    data = summary["prepared"]
    ready = assess_censos_coverage(
        data, summary["parishes_frame"], summary["categories"]
    )
    result = {
        **ready,
        "period": summary["period"],
        "run_id": summary["run_id"],
        "caop_version": "2025",
        "parishes": summary["parishes"],
        "dependency_hashes": summary["dependency_hashes"],
    }
    output = Path(candidate) / "lake/silver/census_reports"
    output.mkdir(parents=True, exist_ok=True)
    data.to_csv(output / "coverage.csv", index=False)
    reports = []
    for scope, column in [
        ("country", None),
        ("region", "autonomous_region"),
        ("municipality", "dico"),
    ]:
        groups = (
            [("PT", data)] if column is None else data.groupby(column, dropna=False)
        )
        for key, group in groups:
            reports.append(
                {
                    "scope": scope,
                    "code": str(key),
                    **{
                        state: int(group.coverage_status.eq(state).sum())
                        for state in ready["counts"]
                    },
                }
            )
    pd.DataFrame(reports).to_csv(output / "summary.csv", index=False)
    orphans = pd.DataFrame(summary["orphans"])
    if orphans.empty:
        orphans = pd.DataFrame(
            columns=["source_dicofre", "age_code", "geography_version", "reason"]
        )
    orphans.to_csv(output / "orphans.csv", index=False)
    (output / "readiness.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8"
    )
    data.to_parquet(Path(candidate) / "prepared/census_coverage.parquet", index=False)
    (Path(candidate) / "lake/silver/census_coverage").mkdir(parents=True, exist_ok=True)
    return result
