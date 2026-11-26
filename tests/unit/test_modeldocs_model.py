"""`load_model` e `run_dbt_parse` (spec 010, T001): manifests sintéticos e o manifest real do projeto."""
import copy

import pytest

from pipelines.modeldocs.model import ModelError, load_model, run_dbt_parse
from tests.fixtures.modeldocs.manifests import (
    ROOT,
    column,
    make_manifest,
    model,
    parse_real_manifest,
)


@pytest.fixture(scope="module")
def real_manifest(tmp_path_factory):
    return parse_real_manifest(tmp_path_factory.mktemp("dbt-parse"))


def demo():
    return make_manifest(
        [model("dim_x", layer="silver", domain="geo", description="Dimensão X.",
               columns=[column("dico", description="Código.", data_type="varchar", tests=["unique", "not_null"]),
                        column("name")]),
         model("fact_a", layer="bronze", domain="obs", columns=[column("dico", tests=["not_null"])], source_ids=["caop"]),
         model("rpt_a_coverage"), model("b_coverage")],
        relationships=[("fact_a", "dico", "source:ext.dim_x", "dico")], sources=["ext.dim_x", "ext.only_source"])


def test_tables_get_layer_domain_kind_description_columns_and_tests():
    tables = {t.name: t for t in load_model(demo()).tables}
    dim, fact = tables["dim_x"], tables["fact_a"]
    assert (dim.layer, dim.domain, dim.kind, dim.description) == ("silver", "geo", "principal", "Dimensão X.")
    assert (fact.layer, fact.domain, fact.description, fact.source_ids) == ("bronze", "obs", None, ("caop",))
    assert [c.name for c in dim.columns] == ["dico", "name"]
    assert dim.columns[0].tests == ("not_null", "unique") and dim.columns[0].data_type == "varchar"
    assert dim.columns[1].description is None and dim.columns[1].tests == () and dim.columns[1].data_type is None
    assert tables["rpt_a_coverage"].kind == tables["b_coverage"].kind == "relatorio"


def test_the_yml_path_is_the_same_with_backslashes_and_with_slashes():
    windows = demo()
    posix = copy.deepcopy(windows)
    for node in posix["nodes"].values():
        for key in ("original_file_path", "patch_path"):
            if node.get(key):
                node[key] = node[key].replace("\\", "/")
    assert load_model(windows) == load_model(posix)
    assert load_model(windows).tables[0].origin_file == "analytics/dbt/models/demo/schema.yml"


def test_relationships_resolve_ref_and_source_to_the_model_and_ignore_singular_tests():
    manifest = make_manifest(
        [model("dim_x", columns=[column("dico")]), model("fact_a", columns=[column("dico"), column("other")])],
        relationships=[("fact_a", "dico", "ref:dim_x", "dico"), ("fact_a", "other", "source:ext.dim_x", "dico")],
        sources=["ext.dim_x"])
    found = load_model(manifest).relationships
    assert [(r.from_column, r.to_table, r.to_column) for r in found] == [("dico", "dim_x", "dico"),
                                                                           ("other", "dim_x", "dico")]
    assert all(r.origin_file == "analytics/dbt/models/demo/schema.yml" for r in found)


def test_an_unreadable_target_is_reported_with_the_file_and_the_model():
    manifest = demo()
    next(n for n in manifest["nodes"].values() if (n.get("test_metadata") or {}).get("name") == "relationships")[
        "test_metadata"]["kwargs"]["to"] = "{{ weird }}"
    with pytest.raises(ModelError, match=r"schema\.yml.*fact_a.*alvo ilegível"):
        load_model(manifest)


def test_the_result_does_not_depend_on_the_node_order():
    manifest = demo()
    reversed_nodes = {**manifest, "nodes": dict(reversed(list(manifest["nodes"].items())))}
    assert load_model(manifest) == load_model(reversed_nodes)


def test_the_real_project_loads_with_every_relationship_resolved(real_manifest):
    loaded = load_model(real_manifest)
    assert len(loaded.tables) >= 25 and len(loaded.relationships) >= 15
    assert {t.layer for t in loaded.tables} == {"bronze", "silver", "gold"}  # gold: spec 011
    assert all(r.to_table in {t.name for t in loaded.tables} for r in loaded.relationships)
    assert all("\\" not in t.origin_file and t.origin_file.startswith("analytics/dbt/") for t in loaded.tables)


def test_run_dbt_parse_returns_the_manifest_and_leaves_no_files_in_the_project(tmp_path):
    project = ROOT / "analytics" / "dbt"
    manifest = run_dbt_parse(project, project, tmp_path / "target")
    assert len([n for n in manifest["nodes"].values() if n["resource_type"] == "model"]) >= 25
    assert not (tmp_path / "target" / "never-opened.duckdb").exists()  # dbt parse never opens the warehouse


def test_run_dbt_parse_fails_clearly_without_the_executable(monkeypatch, tmp_path):
    monkeypatch.setattr("pipelines.modeldocs.model.shutil.which", lambda name: None)
    with pytest.raises(RuntimeError, match="dbt"):
        run_dbt_parse(tmp_path, tmp_path, tmp_path / "target")
