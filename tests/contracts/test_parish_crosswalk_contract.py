"""Locked contracts for the parish crosswalk ingestion (spec 004).

Only public boundaries are exercised: `collect_parish_crosswalk` (with an injected downloader/storage),
`read_crosswalk_table`, `derive_parish_crosswalk` and `verify_coverage`. No network, no dbt.
"""

import hashlib
import json

import pandas as pd
import pytest

from pipelines.collectors.parish_crosswalk.coverage import (
    CrosswalkCoverageError,
    verify_coverage,
)
from pipelines.collectors.parish_crosswalk.derive import derive_parish_crosswalk
from pipelines.collectors.parish_crosswalk.handler import collect_parish_crosswalk
from pipelines.collectors.parish_crosswalk.transform import read_crosswalk_table
from pipelines.collectors.parish_crosswalk.validate import CrosswalkSchemaError
from tests.fixtures.open_meteo.responses import MemoryStorage
from tests.fixtures.parish_crosswalk.tables import (
    LABELS_A,
    ROWS_A,
    ROWS_B,
    UNION_2,
    URL_A,
    URL_B,
    catalog,
    dataset,
    make_table_a,
    make_table_b,
    offline_downloader,
    payloads,
    scenario_frames,
)

KEY_A = "raw/source=ine_parish_crosswalk/dataset=reorganizacao_2013/run_id={run}/reorganizacao_2013.xlsx"
KEY_B = "raw/source=ine_parish_crosswalk/dataset=reposicao_2025/run_id={run}/reposicao_2025.xlsx"


def run(storage, run_id, tmp_path, pay):
    return collect_parish_crosswalk(
        catalog(), storage=storage, downloader=offline_downloader(pay), run_id=run_id,
        collected_at_utc="2026-11-12T12:00:00Z", work_dir=tmp_path / run_id,
    )


def by_id(result):
    return {entry["dataset_id"]: entry for entry in result["datasets"]}


def raw_keys(storage):
    return {key for key in storage.list_keys() if key.startswith("raw/")}


def test_us1_ac1_ac2_ac3_fr002_fr003_fr004_both_tables_are_stored_untouched_and_state_is_per_table(tmp_path):
    storage, pay = MemoryStorage(), payloads(tmp_path)

    first = run(storage, "run-1", tmp_path, pay)
    assert first["status"] == "changed"
    manifest = json.loads(storage.get("manifests/ine_parish_crosswalk/run-1.json"))
    assert manifest["source_id"] == "ine_parish_crosswalk" and manifest["run_id"] == "run-1"
    assert manifest["license_id"] == "CC-BY-4.0" and manifest["collected_at_utc"] == "2026-11-12T12:00:00Z"
    entries = {entry["dataset_id"]: entry for entry in manifest["datasets"]}
    assert set(entries) == {"reorganizacao_2013", "reposicao_2025"}
    for dataset_id, key, url in (("reorganizacao_2013", KEY_A, URL_A), ("reposicao_2025", KEY_B, URL_B)):
        entry = entries[dataset_id]
        assert entry["status"] == "changed" and entry["key"] == key.format(run="run-1") and entry["origin"] == url
        raw = storage.get(entry["key"])
        assert raw == pay[url]  # nem um byte alterado (FR-002)
        assert entry["sha256"] == hashlib.sha256(raw).hexdigest() and entry["bytes"] == len(raw)
    raw_after_first = raw_keys(storage)

    second = run(storage, "run-2", tmp_path, pay)
    assert second["status"] == "unchanged" and {e["status"] for e in second["datasets"]} == {"unchanged"}
    assert raw_keys(storage) == raw_after_first  # nenhum bruto novo

    altered = dict(pay)
    altered[URL_B] = make_table_b(tmp_path / "b2.xlsx", [*ROWS_B, ("090103", "Tres", "Junta", "090151", "Tres")]).read_bytes()
    third = run(storage, "run-3", tmp_path, altered)
    entries3 = by_id(third)
    assert entries3["reposicao_2025"]["status"] == "changed" and entries3["reorganizacao_2013"]["status"] == "unchanged"
    assert raw_keys(storage) - raw_after_first == {KEY_B.format(run="run-3")}  # só a tabela que mudou


def test_us1_ac4_ac5_fr005_invalid_tables_fail_per_table_without_partial_raw_and_recover_next_run(tmp_path):
    storage, good = MemoryStorage(), payloads(tmp_path)
    broken = {
        "html": b"<html><body>Pagina nao encontrada</body></html>",
        "missing column": make_table_a(tmp_path / "x1.xlsx", labels={**LABELS_A, "code": "Outra coluna"}).read_bytes(),
        "wrong sheet": make_table_a(tmp_path / "x2.xlsx", sheet="Plan1").read_bytes(),
        "numeric code that lost its zero": make_table_a(tmp_path / "x3.xlsx", [(10103, "X", "X", "010103")]).read_bytes(),
        "invalid code in a data row": make_table_a(tmp_path / "x4.xlsx", extra=[("ZZ", "Lixo", "Lixo", "9")]).read_bytes(),
    }
    for index, (case, content) in enumerate(broken.items(), start=1):
        run_id = f"bad-{index}"
        first = run(storage, run_id, tmp_path, {**good, URL_A: content})
        entries = by_id(first)
        assert first["status"] == "partial", case
        assert entries["reorganizacao_2013"]["status"] == "failed" and entries["reorganizacao_2013"]["error"], case
        assert entries["reposicao_2025"]["status"] in {"changed", "unchanged"}, case  # a outra tabela segue
        assert KEY_A.format(run=run_id) not in raw_keys(storage), case  # nenhum arquivo parcial da reprovada
        manifest = json.loads(storage.get(f"manifests/ine_parish_crosswalk/{run_id}.json"))
        assert manifest["status"] == "partial", case

    fixed = run(storage, "good-1", tmp_path, good)
    entries = by_id(fixed)  # a falha anterior não impede o novo estado (US1/AC5)
    assert entries["reorganizacao_2013"]["status"] == "changed" and entries["reposicao_2025"]["status"] == "unchanged"


def test_fr005_fr006_reader_keeps_codes_as_text_normalizes_whole_numeric_cells_and_ignores_legends(tmp_path):
    legend = ("Fonte: INE, 2013", None, None, None)
    rows = [("010103 ", " Aguada de Cima ", "Aguada de Cima", "010103"), *ROWS_A[1:6], (None, None, None, None), *ROWS_A[6:]]
    path = make_table_a(tmp_path / "a.xlsx", rows, extra=[legend])

    frame, stats = read_crosswalk_table(dataset("reorganizacao_2013"), path)
    assert list(frame.columns) == ["pre_code", "pre_name", "name_2013", "code_2013", "partial_origin"]
    assert len(frame) == len(ROWS_A) and stats["ignored_rows"] == 1  # a legenda conta; a linha vazia, não
    assert frame["pre_code"].map(type).eq(str).all() and frame["code_2013"].map(len).eq(6).all()
    assert frame.iloc[0].tolist()[:4] == ["010103", "Aguada de Cima", "Aguada de Cima", "010103"]  # sem espaços
    belem = frame[frame["pre_name"] == "São Francisco Xavier"].iloc[0]
    assert (belem["pre_code"], belem["code_2013"]) == ("110640", "110658")  # número de 6 dígitos vira texto
    assert stats["numeric_codes_normalized"] == 2
    assert stats["partial_rows"] == 3 and int(frame["partial_origin"].sum()) == 3  # "(parte)" nas 3 linhas
    assert frame[frame["pre_name"] == "Santa Maria dos Olivais"]["partial_origin"].tolist() == [False]

    frame_b, stats_b = read_crosswalk_table(dataset("reposicao_2025"), make_table_b(tmp_path / "b.xlsx"))
    assert list(frame_b.columns) == ["pre_code", "pre_name", "municipality_name", "code_2025", "name_2025"]
    assert len(frame_b) == len(ROWS_B) and stats_b["ignored_rows"] == 0
    assert {"0308FC", "0308FD"} <= set(frame_b["code_2025"])  # códigos alfanuméricos preservados

    short = make_table_a(tmp_path / "short.xlsx", [(10103, "X", "X", "010103")])
    with pytest.raises(CrosswalkSchemaError, match="10103"):  # 5 dígitos = zero à esquerda perdido
        read_crosswalk_table(dataset("reorganizacao_2013"), short)
    junk = make_table_a(tmp_path / "junk.xlsx", extra=[("ZZ", "Lixo", "Lixo", "9")])
    with pytest.raises(CrosswalkSchemaError, match="ZZ"):  # com dado nas outras colunas não é legenda
        read_crosswalk_table(dataset("reorganizacao_2013"), junk)


# (relation, inherited, partial_origin, name_changed, municipality_changed, pre-2013 codes)
EXPECTED = {
    ("010103", "010103"): ("one_to_one", False, False, False, False, ["010103"]),
    ("010123", "010128"): ("one_to_many", True, False, True, False, ["010101"]),
    ("010123", "010132"): ("one_to_many", True, False, True, False, ["010106"]),
    ("010123", "010133"): ("one_to_many", True, False, True, False, ["010107"]),
    ("010210", "010230"): ("one_to_many", True, False, True, False, ["010201"]),
    ("010210", "010210"): ("one_to_many", True, False, False, False, ["010202"]),  # não reposta: mantém o código
    ("021118", "021118"): ("one_to_many", True, False, False, False, ["021103"]),
    ("021118", "021123"): ("many_to_many", True, True, True, False, ["021113"]),
    ("021122", "021122"): ("one_to_many", True, False, False, False, ["021120"]),
    ("021122", "021123"): ("many_to_many", True, True, True, False, ["021113"]),
    ("030880", "0308FC"): ("one_to_many", True, False, True, False, ["030867"]),
    ("030880", "0308FD"): ("one_to_many", True, False, True, False, ["030869"]),
    ("110658", "110658"): ("one_to_one", False, False, False, False, ["110640"]),
    ("110633", "110633"): ("one_to_one", False, False, False, False, ["110633"]),
    ("110662", "110662"): ("one_to_one", False, True, False, False, ["110633"]),
    ("050101", "050199"): ("one_to_one", False, False, True, False, ["050101"]),
    ("060101", "070150"): ("one_to_one", False, False, False, True, ["060101"]),
    ("090101", "090150"): ("many_to_one", False, False, True, False, ["090101"]),
    ("090102", "090150"): ("many_to_one", False, False, True, False, ["090102"]),
}


def test_us2_ac1_to_ac6_fr007_to_fr011_fr014_pairs_relations_flags_and_determinism():
    table_a, table_b = scenario_frames()

    frame = derive_parish_crosswalk(table_a, table_b)
    assert list(frame.columns) == [
        "dicofre_2013", "name_2013", "dicofre_2025", "name_2025", "relation", "inherited",
        "partial_origin", "name_changed", "municipality_changed", "pre2013_codes",
    ]
    pairs = list(zip(frame["dicofre_2013"], frame["dicofre_2025"], strict=True))
    assert pairs == sorted(EXPECTED) and len(set(pairs)) == len(pairs)  # um par único por linha, em ordem
    got = {
        (row.dicofre_2013, row.dicofre_2025): (
            row.relation, bool(row.inherited), bool(row.partial_origin), bool(row.name_changed),
            bool(row.municipality_changed), list(row.pre2013_codes),
        )
        for row in frame.itertuples()
    }
    assert got == EXPECTED
    unrestored = frame[(frame["dicofre_2013"] == "010210") & (frame["dicofre_2025"] == "010210")].iloc[0]
    assert unrestored["name_2025"] == UNION_2  # não reposta: mesmo código e mesma designação de 2013

    again = derive_parish_crosswalk(table_a.iloc[::-1].reset_index(drop=True), table_b.iloc[::-1].reset_index(drop=True))
    assert again.to_dict("records") == frame.to_dict("records")  # a ordem da entrada não muda o resultado (FR-014)


def test_us3_ac2_ac3_ac4_fr012_coverage_gate_lists_every_gap_by_kind():
    crosswalk = pd.DataFrame({
        "dicofre_2013": ["010103", "010123", "010123"], "dicofre_2025": ["010103", "010128", "010132"],
    })
    dim, codes_2013 = {"010103", "010128", "010132"}, {"010103", "010123"}
    verify_coverage(crosswalk, dim, codes_2013)  # cobertura total: não levanta

    with pytest.raises(CrosswalkCoverageError, match="999999") as without_origin:
        verify_coverage(crosswalk, dim | {"999999"}, codes_2013)
    assert without_origin.value.parishes_without_origin == ["999999"]

    with pytest.raises(CrosswalkCoverageError, match="010199") as without_destination:
        verify_coverage(crosswalk, dim, codes_2013 | {"010199"})
    assert without_destination.value.codes_2013_without_destination == ["010199"]

    with pytest.raises(CrosswalkCoverageError, match="010132") as unknown:
        verify_coverage(crosswalk, dim - {"010132"}, codes_2013)
    assert unknown.value.unknown_destinations == ["010132"]

    with pytest.raises(CrosswalkCoverageError) as everything:
        verify_coverage(crosswalk, (dim - {"010132"}) | {"999999"}, codes_2013 | {"010199"})
    error = everything.value
    assert (error.parishes_without_origin, error.codes_2013_without_destination, error.unknown_destinations) == (
        ["999999"], ["010199"], ["010132"],
    )
    assert all(code in str(error) for code in ("999999", "010199", "010132"))
