"""Build completo da camada Gold com dbt, sobre o fixture offline (spec 011, US1)."""
import hashlib

import pandas as pd
import pytest
import yaml

from pipelines.cli import build_gold as builder
from pipelines.gold.criteria import CriteriaError
from pipelines.gold.prepare import GoldInputError
from tests.fixtures.gold.ci_seed import seed

US1_TABLES = ("gold_municipality_indicator", "gold_rent_by_municipality_typology", "gold_municipality_climate_monthly",
              "gold_criteria_catalog", "gold_criteria_normalization", "gold_data_quality", "gold_parish_indicator",
              "gold_rent_by_parish_typology")


def table(root, name):
    return pd.read_parquet(root / "lake/gold" / name / "data.parquet")


def content(root):
    digest = hashlib.sha256()
    for name in US1_TABLES:
        frame = table(root, name).drop(columns=["processed_at_utc"])
        digest.update(frame.sort_values(list(frame.columns)).to_csv(index=False).encode())
    return digest.hexdigest()


def build(root):
    return builder.build_gold(root, criteria_path=root / "criteria.yml")


def test_full_build_writes_the_us1_tables_and_a_second_build_gives_the_same_content(tmp_path):
    seed(tmp_path)
    result = build(tmp_path)
    for name in US1_TABLES:
        assert (tmp_path / "lake/gold" / name / "data.parquet").is_file(), name
    indicators = table(tmp_path, "gold_municipality_indicator")
    assert (indicators.groupby(["criterion_id", "variant"]).size() == 4).all()  # FR-001: todo município
    assert indicators.loc[indicators["value"].isna(), "missing_reason"].notna().all()
    assert set(indicators["catalog_version"]) == {result["catalog_version"]}
    catalog = table(tmp_path, "gold_criteria_catalog")
    pending = catalog[catalog["status"] == "fonte_pendente"]
    assert pending["criterion_id"].tolist() == ["distancia_sede_distrito_km"] == result["pending"]
    assert "distancia_sede_distrito_km" not in set(indicators["criterion_id"])
    rent = table(tmp_path, "gold_rent_by_municipality_typology")
    assert len(rent) == 4 * 6 and "listing_id" not in rent.columns  # constitution VI: só agregados
    first = content(tmp_path)
    build(tmp_path)
    assert content(tmp_path) == first
    assert not any((tmp_path / ".build/gold").iterdir())  # o candidato sempre é removido


def test_quality_mart_lists_the_whole_catalog_and_matches_the_profile(tmp_path):
    seed(tmp_path)
    build(tmp_path)
    quality = table(tmp_path, "gold_data_quality")
    catalog = table(tmp_path, "gold_criteria_catalog")
    assert set(quality["criterion_id"]) == set(catalog["criterion_id"])  # SC-008
    indicators = table(tmp_path, "gold_municipality_indicator")
    profile = indicators.groupby(["criterion_id", "variant"])["value"].count().to_dict()
    municipal = quality[(quality["level"] == "municipio") & (quality["status"] == "disponivel")]
    assert {(row.criterion_id, row.variant): row.with_value for row in municipal.itertuples()} == profile
    assert (quality["with_value"] + quality["missing"] == quality["territories_expected"]).all()
    pending = quality[quality["status"] == "fonte_pendente"]
    assert pending["pending_reason"].str.startswith("fonte pendente:").all()
    cinema = municipal[municipal["criterion_id"] == "cultura_cinemas_10k"].iloc[0]
    assert cinema["zero_by_convention"] == 1 and cinema["older_period"] == 1
    rent = municipal[(municipal["criterion_id"] == "custo_aluguel_mediana") & (municipal["variant"] == "T2")].iloc[0]
    assert rent["outliers"] == 1


def test_parish_tables_cover_every_parish_and_inherited_rows_copy_the_municipality(tmp_path):
    seed(tmp_path)
    build(tmp_path)
    parish = table(tmp_path, "gold_parish_indicator")
    parishes = pd.read_parquet(tmp_path / "lake/silver/dim_parish/data.parquet")
    assert (parish.groupby(["criterion_id", "variant"])["dicofre"].nunique() == len(parishes)).all()
    rent = table(tmp_path, "gold_rent_by_parish_typology")
    assert set(rent["dicofre"]) == set(parishes["dicofre"]) and len(rent) == len(parishes) * 6
    municipal = table(tmp_path, "gold_municipality_indicator")
    joined = parish[parish["origin"] == "herdado"].merge(municipal, on=["dico", "criterion_id", "variant"],
                                                         suffixes=("", "_m"))
    assert len(joined) and (joined["value"] == joined["value_m"]).all()  # SC-007
    own_rent = parish[(parish["criterion_id"] == "custo_aluguel_mediana") & (parish["origin"] == "proprio")]
    assert set(own_rent["dicofre"]) == {"010101"}
    census = parish[(parish["criterion_id"] == "populacao_residentes") & (parish["dicofre"] == "010102")].iloc[0]
    assert (census["origin"], census["territorial_inheritance"]) == ("proprio", "inherited")


def test_a_failed_dbt_keeps_the_previous_gold_and_removes_the_candidate(tmp_path, monkeypatch):
    seed(tmp_path)
    build(tmp_path)
    before = (tmp_path / "lake/gold/gold_municipality_indicator/data.parquet").read_bytes()

    def boom(*args, **kwargs):
        raise builder.GoldBuildError("dbt simulado falhou")

    monkeypatch.setattr(builder, "_run_dbt", boom)
    with pytest.raises(builder.GoldBuildError, match="simulado"):
        build(tmp_path)
    assert (tmp_path / "lake/gold/gold_municipality_indicator/data.parquet").read_bytes() == before
    assert not any((tmp_path / ".build/gold").iterdir())


def test_an_available_criterion_without_data_fails_naming_it_and_promotes_nothing(tmp_path):
    seed(tmp_path)
    document = yaml.safe_load((tmp_path / "criteria.yml").read_text(encoding="utf-8"))
    cinema = next(item for item in document["criteria"] if item["id"] == "cultura_cinemas_10k")
    cinema["compute"]["dataset_id"] = "dataset_que_nao_existe"
    (tmp_path / "criteria.yml").write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")
    with pytest.raises(CriteriaError, match="'cultura_cinemas_10k'"):
        build(tmp_path)
    assert not (tmp_path / "lake/gold").exists()
    assert not any((tmp_path / ".build/gold").iterdir())


def test_a_missing_input_fails_with_the_table_name(tmp_path):
    seed(tmp_path)
    (tmp_path / "lake/bronze/stg_climate_daily/data.parquet").unlink()
    with pytest.raises(GoldInputError, match="stg_climate_daily"):
        build(tmp_path)
    assert builder.main(["--local", "--root", str(tmp_path), "--criteria", str(tmp_path / "criteria.yml")]) == 1
