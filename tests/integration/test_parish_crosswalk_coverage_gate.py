"""Gate de cobertura no build da correspondência e relatório (spec 004, US3).

A lacuna "código de 2013 sem destino" não pode ser fabricada por arquivos (a tabela A produz um destino por
construção); ela é coberta em `tests/unit/test_parish_crosswalk_coverage.py` e no contrato.
"""

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from pipelines.cli import build_parish_crosswalk as build_module
from pipelines.cli.build_parish_crosswalk import PROMOTED, REPORT_CSV, REVIEW_CSV, main
from tests.fixtures.parish_crosswalk.ci_seed import collect_scenario, write_silver

ATTRIBUTION = "Instituto Nacional de Estatística, IP – Portugal"
# tudo o que uma falha (de cobertura ou do dbt) precisa deixar byte a byte igual
TRACKED = (*(Path(path) / "data.parquet" for path in PROMOTED), Path(REVIEW_CSV), Path(REPORT_CSV))


def _hashes(root: Path) -> dict[Path, str]:
    return {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in TRACKED}


@pytest.fixture
def built(tmp_path):
    write_silver(tmp_path)
    collect_scenario(tmp_path)
    return tmp_path


def test_a_complete_build_promotes_the_report_with_the_totals_and_the_source_statistics(built, capsys):
    assert main(["--local", "--root", str(built)]) == 0
    assert "Cobertura: 17 de 17 freguesias da dim_parish com origem" in capsys.readouterr().out
    report = pd.read_parquet(built / PROMOTED[1] / "data.parquet").set_index("relation")
    assert list(report.index.sort_values()) == ["all", "many_to_many", "many_to_one", "one_to_many", "one_to_one"]
    total = report.loc["all"]
    assert (total["pairs"], total["codes_2013"], total["codes_2025"]) == (19, 13, 17)
    assert (total["parishes_expected"], total["parishes_with_origin"]) == (17, 17)
    assert total["pairs"] == report.drop(index="all")["pairs"].sum()
    assert report.loc["one_to_many", "pairs"] == 9 and report.loc["many_to_many", "pairs"] == 2
    assert (total["source_partial_rows"], total["source_numeric_codes_normalized"]) == (3, 2)
    assert total["caop_version"] == "2025" and total["collected_at_utc"] == "2026-11-12T12:00:00Z"
    assert report.loc["one_to_one", "partial_origin_pairs"] == 1  # o par de Parque das Nações
    assert (built / REVIEW_CSV).is_file()
    assert (report["attribution"] == ATTRIBUTION).all()  # FR-019: a atribuição está em todas as linhas do relatório


def test_the_human_readable_report_is_preserved_with_version_date_and_attribution_on_every_row(built, capsys):
    assert main(["--local", "--root", str(built)]) == 0
    assert "parish_crosswalk_report.csv" in capsys.readouterr().out
    raw = (built / REPORT_CSV).read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # BOM: abre no Excel
    text = raw.decode("utf-8-sig")
    text.encode("cp1252")  # e imprime no console do Windows
    assert ".0;" not in text and ".0\n" not in text  # contagens inteiras, sem ".0"

    report = pd.read_csv(built / REPORT_CSV, sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)
    assert list(report["relation"]) == ["one_to_one", "one_to_many", "many_to_one", "many_to_many", "all"]
    assert set(report["caop_version"]) == {"2025"}  # FR-013 / US3-AC5, também nas linhas que no Parquet ficam vazias
    assert set(report["collected_at_utc"]) == {"2026-11-12T12:00:00Z"}
    assert set(report["attribution"]) == {ATTRIBUTION}  # FR-019
    by_relation = report.set_index("relation")
    assert by_relation.loc["all", "pairs"] == "19" and by_relation.loc["all", "parishes_expected"] == "17"
    assert sum(int(by_relation.loc[name, "pairs"]) for name in list(by_relation.index)[:-1]) == 19
    assert (by_relation.loc[list(by_relation.index)[:-1], "parishes_expected"] == "").all()  # só a linha `all`


@pytest.mark.parametrize(
    ("silver", "message"),
    [
        ({"extra_codes": ("999999",)}, "freguesias da dim_parish sem origem (1): 999999 Freguesia 999999"),
        ({"drop_codes": ("010132",)}, "destinos fora da dim_parish (1): 010132"),
        ({"extra_codes": ("999999",), "drop_codes": ("010132",)}, "cobertura reprovada"),
    ],
)
def test_a_coverage_gap_fails_with_the_codes_and_leaves_the_previous_tables_byte_for_byte(built, capsys, silver, message):
    assert main(["--local", "--root", str(built)]) == 0
    capsys.readouterr()
    before = _hashes(built)

    write_silver(built, **silver)
    assert main(["--local", "--root", str(built)]) == 1
    err = capsys.readouterr().err
    assert "Correspondência: falha: cobertura reprovada" in err and message in err
    assert _hashes(built) == before
    assert not list((built / ".build" / "parish_crosswalk").glob("*"))
    assert not list((built / "lake" / "silver").glob(".previous-*"))


def test_a_failing_dbt_test_also_keeps_the_previous_tables(built, capsys, monkeypatch):
    assert main(["--local", "--root", str(built)]) == 0
    capsys.readouterr()
    before = _hashes(built)

    monkeypatch.setattr(build_module, "verify_coverage", lambda *args, **kwargs: None)  # só a segunda camada age
    write_silver(built, extra_codes=("999999",))
    assert main(["--local", "--root", str(built)]) == 1
    err = capsys.readouterr().err
    assert "dbt build falhou" in err and "parish_crosswalk_every_parish_has_origin" in err
    assert _hashes(built) == before
    assert not list((built / ".build" / "parish_crosswalk").glob("*"))
