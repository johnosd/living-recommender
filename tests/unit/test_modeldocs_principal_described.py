"""As 18 tabelas principais têm descrição, tipo e fonte em todas as colunas declaradas (spec 010, US3, T019).

A lista é fixa de propósito: modelos novos não são cobrados (decisão do autor, sem gate de CI para modelos novos).
Se um modelo desta lista for renomeado ou removido, atualize a lista junto.
"""
import pytest

from pipelines.modeldocs.model import load_model
from pipelines.modeldocs.render import load_sources_info
from tests.fixtures.modeldocs.manifests import ROOT, parse_real_manifest

PRINCIPAL = (
    "stg_caop_municipalities", "stg_caop_parishes", "dim_municipality", "dim_parish", "stg_observation",
    "stg_climate_daily", "xwalk_parish_2013_2025", "idealista_listings", "idealista_occurrences",
    "census_age_category", "census_observation", "census_parish_observation", "wikipedia_revision",
    "wikipedia_article", "wikipedia_section", "wikipedia_block", "dim_mobility_pole",
    "stg_municipality_pole_distance",
)


@pytest.fixture(scope="module")
def principal(tmp_path_factory):
    loaded = load_model(parse_real_manifest(tmp_path_factory.mktemp("dbt-parse")))
    return {table.name: table for table in loaded.tables}, load_sources_info(ROOT / "config" / "sources.yml")


def test_the_fixed_list_is_exactly_the_principal_models_of_the_project(principal):
    tables, _ = principal
    assert {name for name, table in tables.items() if table.kind == "principal"} == set(PRINCIPAL)


@pytest.mark.parametrize("name", PRINCIPAL)
def test_a_principal_table_is_fully_documented(principal, name):
    tables, sources = principal
    table = tables[name]
    assert table.description, f"{name}: sem descrição de tabela"
    assert table.columns, f"{name}: sem colunas declaradas"
    for column in table.columns:
        assert column.description, f"{name}.{column.name}: sem descrição"
        assert column.data_type, f"{name}.{column.name}: sem data_type"
        assert column.data_type == column.data_type.lower(), f"{name}.{column.name}: data_type deve ser minúsculo"
    assert table.source_ids, f"{name}: sem meta.source_ids"
    assert set(table.source_ids) <= set(sources), f"{name}: fonte fora de config/sources.yml"
