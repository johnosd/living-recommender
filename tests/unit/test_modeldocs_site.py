"""`link_sources_to_models` e `lake_catalog_json` (spec 010, T020 e T021)."""
import copy
from datetime import UTC, datetime

from pipelines.modeldocs.model import load_model
from pipelines.modeldocs.site import (
    lake_catalog_json,
    link_relationships,
    link_sources_to_models,
)
from tests.fixtures.modeldocs.lake import write_table
from tests.fixtures.modeldocs.manifests import column, make_manifest, model

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
DIM = "model.caop_territory.dim_municipality"
SOURCE = "source.caop_territory.caop_silver.dim_municipality"


def manifest():
    return make_manifest(
        [model("dim_municipality", layer="silver", columns=[column("dico")]),
         model("stg_a", columns=[column("dico")])],
        relationships=[("stg_a", "dico", "source:caop_silver.dim_municipality", "dico")],
        sources=["caop_silver.dim_municipality", "caop_silver.only_source"])


def test_a_source_with_a_model_of_the_same_name_gets_the_edge_in_both_maps():
    linked = link_sources_to_models(manifest())
    assert linked["parent_map"][SOURCE] == [DIM]
    assert linked["child_map"][DIM] == [SOURCE]


def test_the_input_is_not_changed_and_a_second_application_does_not_duplicate():
    original = manifest()
    snapshot = copy.deepcopy(original)
    once = link_sources_to_models(original)
    assert original == snapshot
    assert link_sources_to_models(once) == once
    assert once["child_map"][DIM].count(SOURCE) == 1


def test_a_source_without_a_model_is_left_alone_and_existing_edges_are_kept():
    base = manifest()
    base["child_map"] = {DIM: ["test.caop_territory.t"]}
    linked = link_sources_to_models(base)
    assert "source.caop_territory.caop_silver.only_source" not in linked["parent_map"]
    assert linked["child_map"][DIM] == ["test.caop_territory.t", SOURCE]


STG = "model.caop_territory.stg_a"


def test_a_declared_relationship_becomes_a_lineage_edge_from_the_target_to_the_model():
    base = manifest()
    linked = link_relationships(base, load_model(base))
    assert linked["parent_map"][STG] == [DIM]
    assert linked["child_map"][DIM] == [STG]


def test_relationship_edges_do_not_change_the_input_duplicate_or_point_a_model_to_itself():
    base = make_manifest(
        [model("dim_municipality", layer="silver", columns=[column("dico"), column("parent_dico")]),
         model("stg_a", columns=[column("dico"), column("other_dico")])],
        relationships=[("stg_a", "dico", "ref:dim_municipality", "dico"),
                       ("stg_a", "other_dico", "ref:dim_municipality", "dico"),
                       ("dim_municipality", "parent_dico", "ref:dim_municipality", "dico")])
    snapshot = copy.deepcopy(base)
    data_model = load_model(base)
    once = link_relationships(base, data_model)
    assert base == snapshot
    assert once["parent_map"][STG] == [DIM] and once["child_map"][DIM] == [STG]  # two tests, one edge
    assert DIM not in once["parent_map"].get(DIM, [])
    assert link_relationships(once, data_model) == once


def test_the_catalog_has_the_real_columns_including_the_undeclared_ones_and_no_values(tmp_path):
    lake = tmp_path / "lake"
    write_table(lake, "silver", "dim_municipality", {"dico": ["0101"], "undeclared": [1.5]})
    catalog = lake_catalog_json(load_model(manifest()), lake, generated_at=NOW)
    node = catalog["nodes"][DIM]
    assert [(c["name"], c["type"], c["index"]) for c in node["columns"].values()] == [
        ("dico", "VARCHAR", 1), ("undeclared", "DOUBLE", 2)]
    assert node["metadata"]["schema"] == "silver" and node["metadata"]["name"] == "dim_municipality"
    assert "0101" not in str(catalog)  # only names and types
    assert catalog["metadata"]["generated_at"] == "2026-11-22T12:00:00Z" and catalog["errors"] is None


def test_a_partial_lake_returns_only_what_exists_and_no_lake_returns_an_empty_catalog(tmp_path):
    lake = tmp_path / "lake"
    write_table(lake, "silver", "dim_municipality", {"dico": ["0101"]})
    partial = lake_catalog_json(load_model(manifest()), lake, generated_at=NOW)
    assert list(partial["nodes"]) == [DIM]  # stg_a has no parquet: no entry, no error
    empty = lake_catalog_json(load_model(manifest()), tmp_path / "missing", generated_at=NOW)
    assert empty["nodes"] == {} and empty["sources"] == {}


def test_the_metadata_comes_from_the_empty_catalog_the_dbt_generated(tmp_path):
    base = {"metadata": {"dbt_schema_version": "https://schemas.getdbt.com/dbt/catalog/v1.json",
                         "dbt_version": "1.12.6", "generated_at": "old"}, "nodes": {}}
    catalog = lake_catalog_json(load_model(manifest()), tmp_path, generated_at=NOW, base=base)
    assert catalog["metadata"]["dbt_version"] == "1.12.6" and catalog["metadata"]["generated_at"].startswith("2026-11-22")
    assert base["metadata"]["generated_at"] == "old"
