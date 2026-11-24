"""`build_catalog`: metadados, inventário do `raw/` e troca atômica do arquivo (spec 010, T008 e T009)."""
from pathlib import Path

import duckdb
import pytest

from pipelines.modeldocs.catalog import build_catalog
from pipelines.modeldocs.model import load_model
from tests.fixtures.modeldocs.lake import write_manifest, write_table
from tests.fixtures.modeldocs.manifests import column, make_manifest, model


def query(path, sql):
    connection = duckdb.connect(str(path), read_only=True)
    try:
        return connection.execute(sql).fetchall()
    finally:
        connection.close()


def build(tmp_path, models, lake=None, manifests=None):
    data = tmp_path / "data"
    for layer, name, columns in lake or []:
        write_table(data / "lake", layer, name, columns)
    for source, run, fields in manifests or []:
        write_manifest(data / "manifests", source, run, **fields)
    output = tmp_path / "out" / "catalog.duckdb"
    result = build_catalog(load_model(make_manifest(models)), lake_root=data / "lake",
                           manifests_root=data / "manifests", output=output)
    return result, output


def test_columns_are_the_union_of_declared_and_real_with_both_types(tmp_path):
    _, output = build(
        tmp_path,
        [model("t", layer="silver", description="T.", columns=[
            column("a", data_type="bigint", description="A."), column("b", data_type="varchar"),
            column("only_declared")])],
        lake=[("silver", "t", {"a": [1, 2], "b": [1.5, 2.5], "extra": ["x", "y"]})])
    rows = {r[0]: r[1:] for r in query(output, "select column_name, position, type_actual, type_declared, declared, "
                                              "in_lake, description from meta.columns order by 1")}
    assert rows["a"] == (1, "BIGINT", "bigint", True, True, "A.")
    assert rows["b"][1:3] == ("DOUBLE", "varchar")  # declared type diverges from the real one
    assert rows["extra"] == (3, "VARCHAR", None, False, True, None)  # real but undeclared
    assert rows["only_declared"] == (None, None, None, True, False, None)  # declared but not in the lake


def test_status_and_row_counts_per_table(tmp_path):
    result, output = build(tmp_path, [model("built", layer="silver"), model("missing")],
                           lake=[("silver", "built", {"x": [1, 2, 3]}), ("bronze", "stray", {"y": [1]})])
    assert result.tables == {"silver.built": "ok", "bronze.missing": "nao_construida", "bronze.stray": "sem_modelo"}
    counts = {(r[0], r[1]): r[2] for r in query(output, "select layer, table_name, row_count from meta.tables")}
    assert counts == {("silver", "built"): 3, ("bronze", "missing"): None, ("bronze", "stray"): 1}
    assert query(output, "select count(*) from information_schema.tables where table_name = 'missing'") == [(0,)]


def test_raw_runs_collect_checksums_at_any_depth_and_fall_back_between_date_keys(tmp_path):
    runs = [("caop", "r1", {"files": [{"sha256": "a1"}], "collected_at_utc": "2026-11-01T00:00:00Z"}),
            ("ine", "r2", {"datasets": [{"sha256": "b1"}, {"sha256": "b2"}]}),
            ("wikipedia", "r3", {"entries": [{"files": [{"sha256": "c1"}]}], "checked_at_utc": "2026-11-03T00:00:00Z"}),
            ("idealista", "r4", {"snapshot_sha256": "d1", "imported_at_utc": "2026-11-04T00:00:00Z"})]
    result, output = build(tmp_path, [], manifests=runs)
    assert result.raw_runs == 4
    rows = {r[0]: r[1:] for r in query(output, "select source_id, checksums, collected_at_utc, manifest_file "
                                              "from meta.raw_runs")}
    assert rows["caop"][:2] == (["a1"], "2026-11-01T00:00:00Z")
    assert rows["ine"][0] == ["b1", "b2"] and rows["ine"][1] is None
    assert rows["wikipedia"][:2] == (["c1"], "2026-11-03T00:00:00Z")
    assert rows["idealista"][:2] == (["d1"], "2026-11-04T00:00:00Z")
    assert rows["caop"][2] == "caop/r1.json"


def test_an_unreadable_manifest_is_skipped_and_reported_without_failing(tmp_path):
    data = tmp_path / "data"
    write_manifest(data / "manifests", "caop", "ok")
    (data / "manifests" / "caop" / "broken.json").write_text("{not json", encoding="utf-8")
    (data / "manifests" / "caop" / "list.json").write_text("[1, 2]", encoding="utf-8")
    result = build_catalog(load_model(make_manifest([])), lake_root=data / "lake", manifests_root=data / "manifests",
                           output=tmp_path / "c.duckdb")
    assert result.raw_runs == 1 and sorted(result.manifests_ignored) == ["caop/broken.json", "caop/list.json"]


def test_without_a_lake_every_model_is_not_built_and_the_file_is_still_created(tmp_path):
    result, output = build(tmp_path, [model("a"), model("b", layer="silver")])
    assert set(result.tables.values()) == {"nao_construida"} and output.exists()
    assert query(output, "select count(*) from meta.columns") == [(0,)]


def test_a_failed_replace_keeps_the_previous_catalog_and_leaves_no_temporary_file(tmp_path, monkeypatch):
    _, output = build(tmp_path, [model("a")], lake=[("bronze", "a", {"x": [1]})])
    before = output.read_bytes()

    def locked(source, target):
        raise PermissionError("o arquivo está em uso")

    monkeypatch.setattr("pipelines.modeldocs.catalog.os.replace", locked)
    with pytest.raises(PermissionError):
        build_catalog(load_model(make_manifest([model("other")])), lake_root=tmp_path / "data" / "lake",
                      manifests_root=tmp_path / "data" / "manifests", output=output)
    assert output.read_bytes() == before
    assert sorted(p.name for p in output.parent.iterdir()) == ["catalog.duckdb"]


def test_a_column_that_is_entirely_null_reports_the_type_without_quotes(tmp_path):
    _, output = build(tmp_path, [model("t", columns=[column("only_null", data_type="null")])],
                      lake=[("bronze", "t", {"only_null": [None, None]})])
    assert query(output, "select type_actual, type_declared from meta.columns") == [("NULL", "null")]


def test_views_keep_an_absolute_path_even_when_the_lake_is_given_as_relative(tmp_path, monkeypatch):
    data = tmp_path / "data"
    write_table(data / "lake", "silver", "t", {"x": [1, 2]})
    monkeypatch.chdir(tmp_path)
    build_catalog(load_model(make_manifest([model("t", layer="silver")])), lake_root=Path("data/lake"),
                  manifests_root=Path("data/manifests"), output=tmp_path / "out" / "c.duckdb")
    definition = query(tmp_path / "out" / "c.duckdb", "select sql from duckdb_views() where view_name = 't'")[0][0]
    assert str(data.resolve().as_posix()) in definition
    monkeypatch.chdir(tmp_path / "out")  # another working directory, as a SQL client has
    assert query(tmp_path / "out" / "c.duckdb", "select count(*) from silver.t") == [(2,)]
