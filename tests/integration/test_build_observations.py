"""Build do staging de observações: promoção segura, falhas sem promoção e a CAOP intacta (US3)."""

import json

import pandas as pd
import pytest

from pipelines.cli import build_caop as caop_builder
from pipelines.cli import build_observations as builder
from pipelines.collectors._shared.storage import LocalStorage
from tests.fixtures.caop.ci_seed import seed as seed_caop
from tests.fixtures.observations.ci_seed import seed

STAGING = "lake/bronze/stg_observation/data.parquet"


def _staging(root):
    return pd.read_parquet(root / STAGING)


def test_build_resolves_every_municipality_and_promotes_the_staging(tmp_path):
    root = tmp_path / "data"
    seed(root, prepare=False)
    result = builder.build_observations(root)
    assert (result["observations"], result["datasets"]) == (12936, 19)
    assert result["not_collected"] == ["pordata/poder_compra_per_capita_xlsx"]
    frame = _staging(root)
    silver = pd.read_parquet(root / "lake/silver/dim_municipality/data.parquet")
    assert set(frame.dico) == set(silver.dico) and frame.dico.notna().all()
    assert not frame.duplicated(["dataset_id", "dico", "period", "filter_1", "filter_2", "filter_3"]).any()
    # as 5 grafias problemáticas do Pordata chegaram ao município certo
    names = frame[(frame.source_id == "pordata") & frame.source_name.isin(
        ["Lagoa", "Lagoa [R.A.A.]", "Calheta [R.A.A.]", "Calheta [R.A.M.]", "Vila da Praia da Vitória"])]
    assert names.groupby("source_name").dico.unique().map(list).to_dict() == {
        "Lagoa": ["0806"], "Lagoa [R.A.A.]": ["4201"], "Calheta [R.A.A.]": ["4501"],
        "Calheta [R.A.M.]": ["3101"], "Vila da Praia da Vitória": ["4302"],
    }
    # ausência explícita: nulo com símbolo; nada virou zero
    assert frame.value.isna().sum() > 0 and (frame.value.isna() & frame.symbol.isna()).sum() == 0
    assert set(frame[frame.source_id == "ine"].license_id) == {"CC-BY-4.0"}
    assert set(frame[frame.source_id == "pordata"].license_id) == {"not_granted_by_source"}
    assert not (root / "lake/gold").exists()


def test_the_manual_dataset_is_skipped_until_it_is_collected(tmp_path):
    root = tmp_path / "data"
    seed(root, prepare=False)
    builder.build_observations(root)
    assert "poder_compra_per_capita_xlsx" not in set(_staging(root).dataset_id)


def test_the_caop_lake_is_left_byte_for_byte_untouched(tmp_path):
    root = tmp_path / "data"
    seed(root, prepare=False)
    caop_files = {
        "lake/bronze/stg_caop_municipalities/data.parquet": b"bronze-caop",
        "lake/silver/dim_parish/data.parquet": b"silver-caop",
    }
    for relative, content in caop_files.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_bytes(content)
    silver = root / "lake/silver/dim_municipality/data.parquet"
    silver_before = silver.read_bytes()
    builder.build_observations(root)
    assert silver.read_bytes() == silver_before
    for relative, content in caop_files.items():
        assert (root / relative).read_bytes() == content


def test_rebuilding_the_caop_does_not_erase_the_observation_staging(tmp_path):
    root = tmp_path / "data"
    seed_caop(root)
    marker = root / STAGING
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_bytes(b"staging-de-observacoes")
    caop_builder.build_caop(root)
    assert marker.read_bytes() == b"staging-de-observacoes"
    assert (root / "lake/silver/dim_municipality/data.parquet").is_file()


def test_unresolved_names_fail_listing_dataset_and_names_and_keep_the_previous_staging(tmp_path, monkeypatch):
    root = tmp_path / "data"
    seed(root, prepare=False)
    builder.build_observations(root)
    before = (root / STAGING).read_bytes()

    monkeypatch.setattr(builder, "load_synonyms", lambda *_: {})
    with pytest.raises(builder.ObservationBuildError) as error:
        builder.build_observations(root)
    message = str(error.value)
    assert "pordata/farmacias" in message and "Lagoa" in message and "Vila da Praia da Vitória" in message
    assert "ine/" not in message  # o INE resolve por código e não depende da seed
    assert (root / STAGING).read_bytes() == before
    assert not list((root / ".build" / "observations").glob("*"))


def test_dbt_failure_does_not_promote(tmp_path, monkeypatch):
    root = tmp_path / "data"
    seed(root, prepare=False)
    builder.build_observations(root)
    before = (root / STAGING).read_bytes()

    def fail(*_):
        raise builder.ObservationBuildError("dbt falhou na fixture")

    monkeypatch.setattr(builder, "_run_dbt", fail)
    with pytest.raises(builder.ObservationBuildError, match="dbt falhou"):
        builder.build_observations(root)
    assert (root / STAGING).read_bytes() == before


def test_missing_silver_and_altered_raw_are_refused(tmp_path):
    empty = tmp_path / "empty"
    with pytest.raises(builder.ObservationBuildError, match="build_caop"):
        builder.build_observations(empty)

    root = tmp_path / "data"
    seed(root, prepare=False)
    storage = LocalStorage(root)
    manifest = json.loads(storage.get("manifests/pordata/ci-obs-pordata.json"))
    storage.local_path(manifest["datasets"][0]["key"]).write_bytes(b"alterado")
    with pytest.raises(builder.ObservationBuildError, match="checksum ou tamanho alterado"):
        builder.build_observations(root)
