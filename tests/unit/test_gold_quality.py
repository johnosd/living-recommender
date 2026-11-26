"""Mart de qualidade (spec 011, US2, data-model.md `gold_data_quality`)."""
import json

import pandas as pd

from pipelines.gold.quality import data_quality


def catalog_row(criterion_id, status="disponivel", levels=("municipio",), pending_reason=None):
    return {"catalog_version": "v1", "criterion_id": criterion_id, "status": status, "levels": json.dumps(list(levels)),
            "pending_reason": pending_reason}


def indicator(dico, criterion_id, value, *, variant="", status=None, older=False, stale=False, source="pordata",
              latest="2024", **extra):
    return {"dico": dico, "criterion_id": criterion_id, "variant": variant, "value": value,
            "value_status": status or ("ausente" if value is None else "observado"), "is_older_period": older,
            "is_stale": stale, "source_id": source, "dataset_latest_period": latest, **extra}


def test_pending_criterion_has_zero_coverage_and_the_reason():
    catalog = pd.DataFrame([catalog_row("p", status="fonte_pendente", levels=("municipio", "freguesia"),
                                        pending_reason="sem polos")])
    quality = data_quality(catalog, {"municipio": pd.DataFrame(columns=["dico", "criterion_id"])}, {})
    assert len(quality) == 2 and set(quality["level"]) == {"municipio", "freguesia"}
    row = quality.iloc[0]
    assert (row["territories_expected"], row["with_value"], row["missing"]) == (0, 0, 0)
    assert row["pending_reason"] == "fonte pendente: sem polos" and row["variant"] == ""


def test_counts_come_from_the_synthetic_rows():
    rows = [indicator("0101", "c", 0.0, status="zero_convencao_fonte"),
            indicator("0102", "c", 3.0, older=True),
            indicator("0103", "c", None),
            indicator("0101", "m", 10.0, stale=True, source="google_distances"),
            indicator("0102", "m", 11.0, source="google_distances"),
            indicator("0103", "m", 12.0, stale=True, source="google_distances"),
            *[indicator(dico, "r", 900.0 if dico == "0101" else None, variant=variant, source="idealista",
                        latest="2026-11") for dico in ("0101", "0102", "0103") for variant in ("ALL", "T2")]]
    rent = pd.DataFrame({"dico": ["0101", "0101", "0102"], "typology": ["ALL", "T2", "T2"], "n_outliers": [2, 1, 3]})
    catalog = pd.DataFrame([catalog_row("c"), catalog_row("m"), catalog_row("r")])
    quality = data_quality(catalog, {"municipio": pd.DataFrame(rows)}, {"municipio": rent})
    row = {(item["criterion_id"], item["variant"]): item for item in quality.to_dict("records")}
    counts = row[("c", "")]
    assert (counts["territories_expected"], counts["with_value"], counts["missing"]) == (3, 2, 1)
    assert (counts["zero_by_convention"], counts["older_period"], counts["outliers"]) == (1, 1, 0)
    assert row[("m", "")]["stale"] == 2 and row[("m", "")]["inherited"] == 0
    assert row[("r", "ALL")]["outliers"] == 2 and row[("r", "T2")]["outliers"] == 4
    assert row[("r", "T2")]["dataset_latest_period"] == "2026-11"


def test_parish_level_counts_only_own_values_and_reports_inherited():
    rows = [{**indicator("0101", "x", 1.0), "dicofre": "010101", "origin": "proprio"},
            {**indicator("0101", "x", 2.0), "dicofre": "010102", "origin": "herdado"},
            {**indicator("0101", "x", None), "dicofre": "010103", "origin": "ausente"}]
    catalog = pd.DataFrame([catalog_row("x", levels=("municipio", "freguesia"))])
    municipal = pd.DataFrame([indicator("0101", "x", 2.0)])
    quality = data_quality(catalog, {"municipio": municipal, "freguesia": pd.DataFrame(rows)}, {})
    parish = quality[quality["level"] == "freguesia"].iloc[0]
    assert (parish["territories_expected"], parish["with_value"], parish["missing"], parish["inherited"]) == (
        3, 1, 2, 1)
