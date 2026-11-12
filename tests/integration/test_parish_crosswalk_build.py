"""Build da correspondência de freguesias sobre a fixture: derivação, dbt e promoção (spec 004, US2)."""

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from pipelines.cli.build_parish_crosswalk import PROMOTED, REVIEW_CSV, main
from pipelines.collectors.parish_crosswalk.derive import CROSSWALK_COLUMNS
from tests.fixtures.parish_crosswalk.ci_seed import (
    collect_scenario,
    expected_crosswalk,
    write_silver,
)
from tests.fixtures.parish_crosswalk.tables import ROWS_A

XWALK = Path(PROMOTED[0]) / "data.parquet"
PROVENANCE = [
    "source_run_id_2013", "source_run_id_2025", "sha256_2013", "sha256_2025",
    "license_id", "attribution", "collected_at_utc", "processed_at_utc",
]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def root(tmp_path):
    write_silver(tmp_path)
    collect_scenario(tmp_path)
    return tmp_path


def test_build_promotes_the_scenario_with_columns_types_provenance_and_the_review_csv(root, capsys):
    assert main(["--local", "--root", str(root)]) == 0
    out = capsys.readouterr().out
    assert "Correspondência: 19 pares" in out and "one_to_one: 6 | one_to_many: 9 | many_to_one: 2 | many_to_many: 2" in out
    frame = pd.read_parquet(root / XWALK)
    assert list(frame.columns) == CROSSWALK_COLUMNS + PROVENANCE
    expected = expected_crosswalk()
    pd.testing.assert_frame_equal(frame[CROSSWALK_COLUMNS].assign(pre2013_codes=frame["pre2013_codes"].map(list)),
                                  expected.assign(pre2013_codes=expected["pre2013_codes"].map(list)))
    for column in ("inherited", "partial_origin", "name_changed", "municipality_changed"):
        assert frame[column].dtype == bool
    assert set(frame["source_run_id_2013"]) == set(frame["source_run_id_2025"]) == {"seed-1"}
    assert set(frame["license_id"]) == {"CC-BY-4.0"} and set(frame["collected_at_utc"]) == {"2026-11-12T12:00:00Z"}
    assert frame["sha256_2013"].str.len().eq(64).all() and frame["sha256_2013"].nunique() == 1

    review = pd.read_csv(root / REVIEW_CSV, sep=";", encoding="utf-8-sig", dtype=str)
    flagged = (expected["relation"] != "one_to_one") | expected[
        ["inherited", "partial_origin", "name_changed", "municipality_changed"]
    ].any(axis=1)
    assert len(review) == int(flagged.sum()) and list(review.columns) == CROSSWALK_COLUMNS
    assert "010123" in set(review["dicofre_2013"]) and "010103" not in set(review["dicofre_2013"])  # 1:1 sem sinal fica fora


def test_cli_output_can_be_printed_on_a_windows_console(root, capsys):
    """O console do Windows usa cp1252: um caractere fora dela (como a seta) derruba o comando depois do build."""
    assert main(["--local", "--root", str(root)]) == 0
    capsys.readouterr().out.encode("cp1252")

    write_silver(root, extra_codes=("999999",))
    assert main(["--local", "--root", str(root)]) == 1
    capsys.readouterr().err.encode("cp1252")


def test_sc005_every_2013_code_converts_to_at_least_one_2025_code_with_the_inheritance_flag(root):
    assert main(["--local", "--root", str(root)]) == 0
    frame = pd.read_parquet(root / XWALK)
    codes_2013 = pd.DataFrame({"dicofre_2013": sorted({str(row[3]) for row in ROWS_A})})
    converted = codes_2013.merge(frame, on="dicofre_2013", how="left")  # uma consulta só
    assert converted["dicofre_2025"].notna().all() and converted["inherited"].notna().all()
    assert set(converted["dicofre_2013"]) == set(codes_2013["dicofre_2013"])
    inherited = converted[converted["dicofre_2013"] == "010123"]
    assert len(inherited) == 3 and inherited["inherited"].all()  # a união desfeita herda, não reparte


def test_sc006_other_tables_keep_their_checksums_and_no_temporary_files_are_left(root):
    other = root / "lake" / "silver" / "dim_municipality" / "data.parquet"
    other.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"dico": ["0101"], "official_name": ["Águeda"]}).to_parquet(other, index=False)
    before = {path: _sha(path) for path in (other, root / "lake" / "silver" / "dim_parish" / "data.parquet")}
    assert main(["--local", "--root", str(root)]) == 0
    assert {path: _sha(path) for path in before} == before
    assert not list((root / "lake" / "silver").glob(".previous-*"))
    assert not list((root / ".build" / "parish_crosswalk").glob("*"))  # o candidato é removido


def test_a_second_build_produces_the_same_table(root):
    assert main(["--local", "--root", str(root)]) == 0
    first = pd.read_parquet(root / XWALK)
    assert main(["--local", "--root", str(root)]) == 0
    second = pd.read_parquet(root / XWALK)
    columns = [c for c in first.columns if c != "processed_at_utc"]
    assert first[columns].astype(str).equals(second[columns].astype(str))


def test_build_fails_clearly_without_dim_parish_without_a_table_or_with_a_tampered_raw(tmp_path, capsys):
    assert main(["--local", "--root", str(tmp_path)]) == 1
    assert "build_caop" in capsys.readouterr().err

    write_silver(tmp_path)
    assert main(["--local", "--root", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "reorganizacao_2013" in err and "collect_parish_crosswalk" in err
    assert not (tmp_path / XWALK).exists()

    collect_scenario(tmp_path)
    raw = next((tmp_path / "raw").rglob("reorganizacao_2013.xlsx"))
    raw.write_bytes(raw.read_bytes() + b"x")
    assert main(["--local", "--root", str(tmp_path)]) == 1
    assert "checksum ou tamanho alterado" in capsys.readouterr().err
    assert not (tmp_path / XWALK).exists()
