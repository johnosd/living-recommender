"""CSV do Pordata e JSON do INE → observações em formato longo (símbolos, ausência, agregação)."""

import json

import pandas as pd
import pytest

from pipelines.cli._promote import promote_paths
from pipelines.collectors._shared.catalog import get_dataset_source, load_catalog
from pipelines.collectors._shared.observations import COLUMNS, finalize
from pipelines.collectors.ine.transform import read_ine_response
from pipelines.collectors.pordata.transform import read_pordata_csv
from tests.fixtures.ine.responses import CRIME_CATEGORIES, ine_response
from tests.fixtures.pordata.layouts import pordata_csv

CATALOG = load_catalog()
PORDATA = get_dataset_source(CATALOG, "pordata")["datasets"][0]
INE = {d["id"]: d for d in get_dataset_source(CATALOG, "ine")["datasets"]}


def _csv(tmp_path, text):
    path = tmp_path / "d.csv"
    path.write_text(text, encoding="utf-8", newline="")
    return path


@pytest.mark.parametrize("layout", ["a", "b", "c"])
def test_every_layout_yields_municipal_rows_only_and_counts_the_aggregates(tmp_path, layout):
    frame, excluded = read_pordata_csv(PORDATA, _csv(tmp_path, pordata_csv(layout)))
    assert len(frame) == 4  # 2 municípios × 2 anos
    assert excluded == (1 if layout == "a" else 2)  # Portugal (+ a linha de país nos layouts b e c)
    assert set(frame.source_name) == {"Évora", "Lagoa"}
    assert frame.period.tolist() == [2023, 2024, 2023, 2024] and frame.period.dtype == "int64"
    assert set(frame.unit) == {"farmácias"}  # o espaço inicial de `Escala` é removido
    assert frame.value.tolist() == [100.0, 101.0, 110.0, 111.0]


def test_missing_value_stays_null_with_its_symbol_and_revised_values_keep_theirs(tmp_path):
    frame, _ = read_pordata_csv(PORDATA, _csv(tmp_path, pordata_csv("a", with_symbols=True)))
    evora_last, lagoa_last = frame.iloc[1], frame.iloc[3]
    assert pd.isna(evora_last.value) and evora_last.symbol == "x"  # ausente: nunca vira 0
    assert lagoa_last.value == 111.0 and lagoa_last.symbol == "r"
    assert (frame.value.isna() & frame.symbol.isna()).sum() == 0
    assert frame.symbol.isna().sum() == 2  # as demais linhas não têm símbolo


def test_filters_are_read_by_label(tmp_path):
    frame, _ = read_pordata_csv(PORDATA, _csv(tmp_path, pordata_csv("b", filter_1="Homens")))
    assert set(frame.filter_1) == {"Homens"} and set(frame.filter_2) == {""}


def _ine(tmp_path, text, dataset):
    path = tmp_path / "r.json"
    path.write_text(text, encoding="utf-8")
    return read_ine_response(dataset, path)


def test_ine_absence_keeps_the_conventional_symbol_and_never_becomes_zero(tmp_path):
    frame, excluded = _ine(tmp_path, ine_response("0014698"), INE["rendas_novos_contratos"])
    assert excluded == 0 and len(frame) == 8  # 4 municípios × 2 períodos
    missing = frame[frame.source_name == "1C40701"]
    assert missing.value.isna().all() and set(missing.symbol) == {"-"}
    assert frame.value.notna().sum() == 6 and set(frame.unit) == {"€/m²"}
    assert sorted(frame.period.unique()) == [2024, 2025]


def test_ine_crime_category_goes_to_filter_1_and_non_municipal_codes_are_excluded(tmp_path):
    document = json.loads(ine_response("0008074", categories=CRIME_CATEGORIES, periods=("2022",)))
    document[0]["Dados"]["2022"].append({"geocod": "PT", "geodsg": "Portugal", "valor": "9", "ind_string": "9"})
    frame, excluded = _ine(tmp_path, json.dumps(document), INE["taxa_criminalidade"])
    assert excluded == 1
    assert set(frame.filter_1) == {"Total", "Crimes contra a integridade física", "Crimes contra o patrimônio"}
    assert len(frame) == 4 * 3 and set(frame.unit) == {"‰"}


def test_finalize_adds_the_resolved_municipality_and_the_provenance(tmp_path):
    frame, _ = read_pordata_csv(PORDATA, _csv(tmp_path, pordata_csv("a")))
    source = get_dataset_source(CATALOG, "pordata")
    state = {"run_id": "run-9", "collected_at_utc": "2026-11-11T12:00:00Z"}
    dico = frame.source_name.map({"Évora": "0705", "Lagoa": "0806"})
    result = finalize(frame, source=source, dataset=PORDATA, state=state, dico=dico,
                      processed_at_utc="2026-11-11T13:00:00Z")
    assert list(result.columns) == COLUMNS
    assert set(result.dico) == {"0705", "0806"} and set(result.source_id) == {"pordata"}
    assert set(result.license_id) == {"not_granted_by_source"} and set(result.source_run_id) == {"run-9"}
    assert set(result.collected_at_utc) == {"2026-11-11T12:00:00Z"}
    assert set(result.processed_at_utc) == {"2026-11-11T13:00:00Z"}  # coleta e processamento separados


def test_promote_paths_replaces_only_the_named_tables_and_rolls_back_on_failure(tmp_path):
    root, candidate = tmp_path / "root", tmp_path / "candidate"
    (root / "lake/bronze/stg_caop").mkdir(parents=True)
    (root / "lake/bronze/stg_caop/data.parquet").write_text("caop")
    (root / "lake/bronze/stg_observation").mkdir(parents=True)
    (root / "lake/bronze/stg_observation/data.parquet").write_text("antigo")
    (candidate / "lake/bronze/stg_observation").mkdir(parents=True)
    (candidate / "lake/bronze/stg_observation/data.parquet").write_text("novo")

    promoted = promote_paths(root, candidate, ["lake/bronze/stg_observation", "lake/bronze/rpt_ausente"])
    assert promoted == ["lake/bronze/stg_observation"]
    assert (root / "lake/bronze/stg_observation/data.parquet").read_text() == "novo"
    assert (root / "lake/bronze/stg_caop/data.parquet").read_text() == "caop"  # irmã intocada
    assert not list((root / "lake/bronze").glob(".previous-*"))
