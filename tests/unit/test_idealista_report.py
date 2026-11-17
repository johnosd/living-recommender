"""FR-005: recortes reconciliados entre JSON, CSV e Markdown, sem dados individuais."""

import json

import pandas as pd
import pytest

from pipelines.collectors.idealista.report import write_report


def test_municipal_breakdowns_reconcile_across_formats_and_preserve_sample_rules(tmp_path):
    def row(dico, typology, price, conflict=""):
        return {"dico": dico, "typology": typology, "asking_rent_eur": price,
                "conflict_fields": conflict, "listing_id": "private-listing-id",
                "address": "private-address", "locality_level": "regiao" if dico is None else "municipio",
                "source_region": "Região sintética", "locality_raw": "Distrito sintético"}

    rows = [row("0001", "T1", 100 * i) for i in range(1, 11)]
    rows += [row("0001", "T1", 50000, "area_m2|asking_rent_eur"), row("0001", "T1", None)]
    rows += [row("0001", "T2", 900) for _ in range(9)] + [row("0001", None, None)]
    rows += [row("0002", "T1", 200) for _ in range(10)]
    rows += [row(None, "T1", 9000) for _ in range(10)]
    municipalities = pd.DataFrame({"dico": ["0001", "0002", "0003"],
                                   "official_name": ["Alfa", "Beta", "Sem amostra"]})
    summary = {"snapshot_month": "2026-11", "source_run_id": "synthetic-report",
               "snapshot_sha256": "b" * 64, "license_id": "restricted", "attribution": "Fonte sintética"}
    write_report(pd.DataFrame(rows), municipalities, summary, tmp_path)

    statistics = json.loads((tmp_path / "statistics.json").read_text(encoding="utf-8"))
    expected = {
        ("0001", "T1"): (12, 10, 325, 550, 775),
        ("0001", "T2"): (9, 9, None, None, None),
        ("0001", "não informada"): (1, 0, None, None, None),
        ("0002", "T1"): (10, 10, 200, 200, 200),
    }
    groups = statistics["municipality_typology_stats"]
    assert {(r["dico"], r["typology"]) for r in groups} == set(expected)
    for group in groups:
        assert tuple(group[k] for k in ("n_listings", "n_eligible", "p25_eur", "median_eur", "p75_eur")) == expected[
            group["dico"], group["typology"]]
    assert groups[0]["n_price_conflicts"] == 1
    municipal = {r["dico"]: r for r in statistics["municipality_stats"]}
    assert set(municipal) == {"0001", "0002", "0003"}
    assert (municipal["0001"]["n_listings"], municipal["0001"]["n_eligible"]) == (22, 19)
    assert municipal["0003"]["n_listings"] == municipal["0003"]["n_eligible"] == 0
    assert municipal["0003"]["median_eur"] is None
    assert sum(r["n_listings"] for r in groups) == sum(r["n_listings"] for r in municipal.values()) == 32
    assert statistics["lot"]["n_listings"] == 42  # regionais não são distribuídos pelos municípios

    for key in ("municipality_stats", "municipality_typology_stats"):
        csv = pd.read_csv(tmp_path / f"{key}.csv", sep=";", dtype={"dico": str})
        assert len(csv) == len(statistics[key])
        for actual, expected_row in zip(csv.to_dict("records"), statistics[key], strict=True):
            assert actual.keys() == expected_row.keys()
            for field, value in expected_row.items():
                if value is None:
                    assert pd.isna(actual[field])
                elif isinstance(value, float):
                    assert actual[field] == pytest.approx(value)
                else:
                    assert actual[field] == value

    markdown = (tmp_path / "report.md").read_text(encoding="utf-8")
    breakdown = markdown.split("### Por município e tipologia\n", 1)[1].split("### Grupos regionais", 1)[0]
    assert "| Alfa (0001) / T1 | 12 | 10 | € 325,00 | € 550,00 | € 775,00 | amostra suficiente |" in breakdown
    assert "| Alfa (0001) / T2 | 9 | 9 | — | — | — | amostra insuficiente |" in breakdown
    assert "| Alfa (0001) / não informada | 1 | 0 | — | — | — | amostra insuficiente |" in breakdown
    assert "| Beta (0002) / T1 | 10 | 10 | € 200,00 | € 200,00 | € 200,00 | amostra suficiente |" in breakdown
    assert sum(line.startswith("| ") for line in breakdown.splitlines()) == 6
    for path in tmp_path.iterdir():
        content = path.read_text(encoding="utf-8-sig")
        assert "private-listing-id" not in content and "private-address" not in content


def test_empty_report_keeps_municipalities_and_has_no_phantom_typology_groups(tmp_path):
    listings = pd.DataFrame({"dico": pd.Series(dtype="string"), "typology": pd.Series(dtype="string"),
                             "asking_rent_eur": pd.Series(dtype="Float64"),
                             "conflict_fields": pd.Series(dtype="string")})
    municipalities = pd.DataFrame({"dico": ["0001"], "official_name": ["Alfa"]})
    summary = {"snapshot_month": "2026-11", "source_run_id": "empty", "snapshot_sha256": "c" * 64,
               "license_id": "restricted", "attribution": "Fonte sintética"}
    result = write_report(listings, municipalities, summary, tmp_path)
    assert result["municipality_typology_stats"] == []
    assert len(result["municipality_stats"]) == 1
    assert result["municipality_stats"][0]["n_listings"] == result["municipality_stats"][0]["n_eligible"] == 0
    assert result["municipality_stats"][0]["median_eur"] is None
    assert pd.read_csv(tmp_path / "municipality_typology_stats.csv", sep=";").empty
    assert "### Por município e tipologia" in (tmp_path / "report.md").read_text(encoding="utf-8")
