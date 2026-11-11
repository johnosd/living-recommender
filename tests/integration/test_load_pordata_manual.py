"""Carga manual da planilha do Pordata: bruto rastreável, estado próprio e staging (US5)."""

import hashlib
import json

import pandas as pd

from pipelines.cli import build_observations as builder
from pipelines.cli.load_pordata_manual import main
from pipelines.collectors._shared.storage import LocalStorage
from tests.fixtures.observations.ci_seed import municipalities, seed
from tests.fixtures.pordata.xlsx import make_pordata_xlsx

DATASET = "poder_compra_per_capita_xlsx"
NAMES = [pordata for _, pordata in municipalities().values()]


def _raw(storage):
    return {key for key in storage.list_keys() if key.startswith("raw/")}


def _last_manifest(storage):
    return json.loads(storage.get(max(k for k in storage.list_keys() if k.startswith("manifests/"))))


def test_us5_changed_then_unchanged_then_changed_and_the_operator_file_is_never_touched(tmp_path, capsys):
    root, source = tmp_path / "lake", make_pordata_xlsx(tmp_path / "poder.xlsx", NAMES)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    argv = ["--local", "--root", str(root), "--file", str(source)]
    assert main(argv) == 0
    assert "Pordata (manual): changed" in capsys.readouterr().out
    storage = LocalStorage(root)
    raw = _raw(storage)
    (key,) = raw
    assert f"dataset={DATASET}/run_id=" in key and key.endswith(".xlsx")
    manifest = _last_manifest(storage)
    entry = manifest["datasets"][0]
    assert entry["dataset_id"] == DATASET and entry["status"] == "changed"
    # a planilha foi entregue à mão: nem o dataset nem a execução podem dizer `http_download`
    assert entry["collection_method"] == "manual_upload" and manifest["collection_method"] == "manual_upload"
    assert entry["sha256"] == before and storage.get(entry["key"]) == source.read_bytes()

    assert main(argv) == 0
    assert "Pordata (manual): unchanged" in capsys.readouterr().out
    assert _raw(storage) == raw

    make_pordata_xlsx(source, NAMES, value_offset=1.0)  # uma nova exportação
    assert main(argv) == 0
    assert len(_raw(storage)) == 2
    assert hashlib.sha256(source.read_bytes()).hexdigest() != before  # só mudou porque o operador a refez


def test_an_invalid_workbook_fails_with_the_reason_and_leaves_nothing_in_raw(tmp_path, capsys):
    root = tmp_path / "lake"
    source = make_pordata_xlsx(tmp_path / "curta.xlsx", NAMES[:100])
    assert main(["--local", "--root", str(root), "--file", str(source)]) == 1
    out = capsys.readouterr().out
    assert "failed" in out and "100 linhas" in out
    storage = LocalStorage(root)
    assert _raw(storage) == set() and _last_manifest(storage)["status"] == "failed"


def test_a_missing_file_or_an_unknown_dataset_is_refused_before_writing_anything(tmp_path, capsys):
    root = tmp_path / "lake"
    assert main(["--local", "--root", str(root), "--file", str(tmp_path / "nao_existe.xlsx")]) == 1
    assert "arquivo não encontrado" in capsys.readouterr().err
    source = make_pordata_xlsx(tmp_path / "p.xlsx", NAMES)
    assert main(["--local", "--root", str(root), "--file", str(source), "--dataset", "farmacias"]) == 1
    assert "não por carga manual" in capsys.readouterr().err
    assert main(["--local", "--root", str(root), "--file", str(source), "--dataset", "inexistente"]) == 1
    assert "dataset não cadastrado" in capsys.readouterr().err
    assert LocalStorage(root).list_keys() == set()


def test_the_manual_dataset_enters_the_staging_with_the_municipality_resolved(tmp_path):
    root = tmp_path / "data"
    seed(root, prepare=False)
    source = make_pordata_xlsx(tmp_path / "p.xlsx", NAMES)
    assert main(["--local", "--root", str(root), "--file", str(source)]) == 0

    result = builder.build_observations(root)
    assert result["datasets"] == 20 and result["not_collected"] == []
    staging = pd.read_parquet(root / "lake/bronze/stg_observation/data.parquet")
    manual = staging[staging.dataset_id == DATASET]
    assert len(manual) == 308 * 2 and set(manual.period) == {2019, 2021}
    assert set(manual[manual.source_name == "Lagoa [R.A.A.]"].dico) == {"4201"}
    assert set(manual[manual.source_name == "Lagoa"].dico) == {"0806"}
    assert set(manual.license_id) == {"not_granted_by_source"}
    coverage = result["coverage"].set_index("dataset_id").loc[DATASET]
    assert coverage.municipalities_with_value == 308 and coverage.aggregate_rows_excluded == 4
