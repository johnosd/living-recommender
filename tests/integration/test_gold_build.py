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
              "gold_rent_by_parish_typology", "gold_rent_by_district_typology", "gold_rent_by_region_typology")


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
    own = indicators.assign(value=indicators["value"].where(indicators["origin"] == "proprio"))  # spec 012, FR-014
    profile = own.groupby(["criterion_id", "variant"])["value"].count().to_dict()
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


def test_the_district_and_region_tables_aggregate_every_listing_of_the_area(tmp_path):
    seed(tmp_path)
    build(tmp_path)  # spec 012, US1
    districts = table(tmp_path, "gold_rent_by_district_typology")
    regions = table(tmp_path, "gold_rent_by_region_typology")
    assert set(districts["district_or_island"]) == {"Aveiro", "Ilha da Madeira"} and len(districts) == 2 * 6
    assert set(regions["source_region"]) == {"Centro", "Madeira"} and len(regions) == 2 * 6
    for frame in (districts, regions):
        assert not {"listing_id", "dico", "dicofre"} & set(frame.columns)  # constitution IV: só agregados
        assert frame.loc[frame["n_eligible"] < 10, "rent_median"].isna().all()
    aveiro = districts.set_index(["district_or_island", "typology"]).loc[("Aveiro", "ALL")]
    assert aveiro["n_listings"] == 13 + 3 + 10 and aveiro["source_region"] == "Centro"  # 0101, 0102 e só distrito
    madeira = districts.set_index(["district_or_island", "typology"]).loc[("Ilha da Madeira", "ALL")]
    assert madeira["sample_status"] == "amostra_insuficiente" and pd.isna(madeira["rent_median"])


def test_a_municipality_without_sample_inherits_the_district_and_normalization_stays_own(tmp_path):
    seed(tmp_path)
    build(tmp_path)  # spec 012, US2
    indicators = table(tmp_path, "gold_municipality_indicator")
    rent = indicators[indicators["criterion_id"] == "custo_aluguel_mediana"].set_index(["dico", "variant"])
    districts = table(tmp_path, "gold_rent_by_district_typology").set_index(["district_or_island", "typology"])
    assert (rent.loc[("0101", "ALL"), "origin"], rent.loc[("0101", "ALL"), "origin_level"]) == (
        "proprio", "municipio")
    for variant in ("ALL", "T2"):
        row = rent.loc[("0102", variant)]
        assert (row["origin"], row["origin_level"]) == ("herdado", "distrito")
        assert row["value"] == districts.loc[("Aveiro", variant), "rent_median"] != rent.loc[("0101", variant), "value"]
    for dico, reason in (("1106", "sem_anuncios"), ("3101", "regional_only")):  # sem referência em nenhum nível
        row = rent.loc[(dico, "ALL")]
        assert row["origin"] == "ausente" and pd.isna(row["origin_level"]) and row["missing_reason"] == reason
    others = indicators[indicators["criterion_id"] != "custo_aluguel_mediana"]
    assert (others["origin"] == others["value"].notna().map({True: "proprio", False: "ausente"})).all()
    normalization = table(tmp_path, "gold_criteria_normalization")
    municipal = normalization[(normalization["criterion_id"] == "custo_aluguel_mediana")
                              & (normalization["level"] == "municipio")]
    assert municipal["n"].tolist() == [1, 1]  # só 0101: o herdado de 0102 não normaliza
    table_rent = table(tmp_path, "gold_rent_by_municipality_typology").set_index(["dico", "typology"])
    inherited = table_rent.loc[("0102", "ALL")]
    assert (inherited["rent_coverage"], inherited["reference_level"]) == ("insuficiente", "distrito")


def test_the_parish_keeps_the_source_level_and_quality_counts_inherited_values_apart(tmp_path):
    seed(tmp_path)
    build(tmp_path)  # spec 012, US3
    parish = table(tmp_path, "gold_parish_indicator")
    rent = parish[(parish["criterion_id"] == "custo_aluguel_mediana") & (parish["variant"] == "ALL")]
    levels = {row.dicofre: (row.origin, None if pd.isna(row.origin_level) else row.origin_level)
              for row in rent.itertuples()}
    assert levels == {"010101": ("proprio", "freguesia"), "010102": ("herdado", "municipio"),
                      "010201": ("herdado", "distrito"), "110601": ("ausente", None), "310101": ("ausente", None)}
    quality = table(tmp_path, "gold_data_quality")
    quality = quality[(quality["criterion_id"] == "custo_aluguel_mediana") & (quality["variant"] == "ALL")]
    counts = quality.set_index("level")[["territories_expected", "with_value", "missing", "inherited",
                                         "inherited_municipio", "inherited_distrito", "inherited_regiao"]]
    assert counts.loc["freguesia"].tolist() == [5, 1, 4, 2, 1, 1, 0]
    assert counts.loc["municipio"].tolist() == [4, 1, 3, 1, 0, 1, 0]


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
