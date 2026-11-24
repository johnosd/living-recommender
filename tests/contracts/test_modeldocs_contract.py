"""Locked contracts for the data model visibility feature (spec 010).

Only public boundaries are exercised: `load_model`, `render_markdown`, `build_catalog` and the `model_docs` CLI
`main`. The real dbt project is parsed once (no warehouse, no lake, no network); every other scenario uses the
hand-made manifests of `tests/fixtures/modeldocs/manifests.py`.
"""

import json
import re

import duckdb
import pytest

from pipelines.cli import model_docs as cli
from pipelines.modeldocs.catalog import build_catalog
from pipelines.modeldocs.model import ModelError, load_model
from pipelines.modeldocs.render import load_sources_info, render_markdown
from tests.fixtures.modeldocs.lake import snapshot, write_manifest, write_table
from tests.fixtures.modeldocs.manifests import (
    ROOT,
    column,
    make_manifest,
    model,
    parse_real_manifest,
)

EDGE = re.compile(r"^\s+(\w+) \}o--\|\| (\w+) : \"(\w+) -> (\w+)\"$", re.MULTILINE)


@pytest.fixture(scope="module")
def real_manifest(tmp_path_factory):
    return parse_real_manifest(tmp_path_factory.mktemp("dbt-parse"))


def sections(document: str) -> dict[str, str]:
    """Split by `### ` headings: heading text -> body."""
    parts = re.split(r"^### (.+)$", document, flags=re.MULTILINE)
    return {parts[i].strip(): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def demo_manifest():
    return make_manifest(
        [model("dim_x", layer="silver", description="Dimensão X.",
               columns=[column("dico", description="Código do município.", tests=["not_null", "unique"])]),
         model("fact_a", description="", columns=[column("dico", tests=["not_null"])]),
         model("rpt_a_coverage", description="Cobertura de A.", columns=[column("n")])])


def test_the_document_is_complete_deterministic_and_free_of_values_and_local_paths(real_manifest):
    # US1-AC1, AC2, AC5, SC-001, FR-005, FR-006
    sources = load_sources_info(ROOT / "config" / "sources.yml")
    document = render_markdown(load_model(real_manifest), sources)
    nodes = real_manifest["nodes"].values()
    names = {n["name"] for n in nodes if n["resource_type"] == "model"}
    assert len(names) >= 25 and all(f"### {name}\n" in document for name in names)
    declared = [n for n in nodes if n["resource_type"] == "test"
                and (n.get("test_metadata") or {}).get("name") == "relationships"]
    edges = EDGE.findall(document)
    assert len(declared) >= 15 and len(edges) == len(declared)
    assert ("stg_municipality_pole_distance", "dim_municipality", "dico", "dico") in edges  # source -> other build
    shuffled = {**real_manifest, "nodes": dict(reversed(list(real_manifest["nodes"].items())))}
    assert render_markdown(load_model(shuffled), sources) == document  # same bytes whatever the manifest order
    assert "\r" not in document and ".data" not in document and "\\" not in document
    assert not re.search(r"[A-Za-z]:[\\/]", document) and not re.search(r"\d{8}T\d{6}", document)  # paths, run ids


def test_gaps_are_explicit_never_invented_and_territorial_keys_without_a_relationship_are_listed():  # US1-AC3, FR-003/018
    document = render_markdown(load_model(demo_manifest()), {})
    parts = sections(document)
    assert "sem descrição" in document and "- fact_a\n" in parts["Sem descrição"]
    assert "- fact_a.dico\n" in parts["Chaves territoriais sem relacionamento declarado"]
    assert "dim_x.dico" not in parts["Chaves territoriais sem relacionamento declarado"]  # it is the table's own key
    coverage = parts["Cobertura de descrição"]
    assert "67%" in coverage and "33%" in coverage  # tables 2/3 and columns 1/3, rounded half up


def test_a_relationship_to_a_table_that_does_not_exist_fails_naming_file_model_and_target():  # FR-009
    manifest = make_manifest([model("fact_a", yml="demo/schema.yml", columns=[column("dico")])],
                             relationships=[("fact_a", "dico", "source:ext.ghost_table", "dico")],
                             sources=["ext.ghost_table"])
    with pytest.raises(ModelError) as error:
        load_model(manifest)
    message = str(error.value)
    assert "analytics/dbt/models/demo/schema.yml" in message and "fact_a" in message and "ghost_table" in message


def test_check_mode_flags_a_stale_document_names_the_regenerating_command_and_ignores_line_endings(tmp_path, capsys):
    manifest_path, output = tmp_path / "manifest.json", tmp_path / "modelo_de_dados.md"
    manifest_path.write_text(json.dumps(demo_manifest()), encoding="utf-8")
    args = ["--manifest", str(manifest_path), "--output", str(output), "--sources", str(ROOT / "config/sources.yml")]
    assert cli.main(args) == 0 and b"\r" not in output.read_bytes()  # always written with LF
    assert cli.main([*args, "--check"]) == 0
    output.write_bytes(output.read_bytes().replace(b"\n", b"\r\n"))  # what Git does on Windows (autocrlf)
    assert cli.main([*args, "--check"]) == 0
    changed = demo_manifest()
    changed["nodes"]["model.caop_territory.fact_a"]["description"] = "Agora descrito."
    manifest_path.write_text(json.dumps(changed), encoding="utf-8")
    capsys.readouterr()
    assert cli.main([*args, "--check"]) == 1
    captured = capsys.readouterr()
    assert "pipelines.cli.model_docs" in captured.out + captured.err  # tells how to regenerate
    output.unlink()
    assert cli.main([*args, "--check"]) == 1  # a missing document is also stale


def test_the_catalog_exposes_every_lake_table_without_copying_or_touching_the_lake(tmp_path):  # US2-AC1/2/3/5/6/7
    data, out = tmp_path / "data", tmp_path / "out" / "catalog.duckdb"
    lake, manifests = data / "lake", data / "manifests"
    write_table(lake, "silver", "dim_municipality", {"dico": ["0101", "0102", "0201"], "name": ["A", "B", "C"]})
    write_table(lake, "bronze", "stg_obs", {"dico": ["0101", "0101", "0102", "0201", "0201"],
                                                  "value": [1.0, 2.0, 3.0, 4.0, 5.0]})
    write_table(lake, "silver", "orphan", {"x": [1]})  # parquet without a dbt model
    (lake / "bronze").joinpath("report.csv").write_text("a;b\n1;2\n", encoding="utf-8")  # not a table: ignored
    write_manifest(manifests, "caop", "20261101T000000000000Z-aaaa", collected_at_utc="2026-11-01T00:00:00Z")
    write_manifest(manifests, "pordata", "20261102T000000000000Z-bbbb", status="unchanged",
                   datasets=[{"sha256": "ab" * 32}])
    manifest = make_manifest(
        [model("dim_municipality", layer="silver", columns=[column("dico", tests=["unique"]), column("name")]),
         model("stg_obs", columns=[column("dico"), column("value")]), model("ghost_table")],
        relationships=[("stg_obs", "dico", "ref:dim_municipality", "dico")])
    before = snapshot(data)

    result = build_catalog(load_model(manifest), lake_root=lake, manifests_root=manifests, output=out)

    assert result.tables == {"silver.dim_municipality": "ok", "bronze.stg_obs": "ok",
                             "bronze.ghost_table": "nao_construida", "silver.orphan": "sem_modelo"}
    assert result.raw_runs == 2 and any("report.csv" in item for item in result.ignored)
    assert snapshot(data) == before  # raw, lake and manifests untouched (read only)
    assert out.stat().st_size < 5_000_000  # views and metadata only: nothing is copied
    con = duckdb.connect(str(out), read_only=True)
    assert con.execute("select count(*) from silver.dim_municipality").fetchone()[0] == 3
    assert con.execute("select count(*) from bronze.stg_obs o join silver.dim_municipality d using (dico)"
                       ).fetchone()[0] == 5  # cross-source join with no extra setup
    assert con.execute("select count(*) from meta.raw_runs").fetchone()[0] == 2
    for meta in ("tables", "columns", "relationships"):
        assert con.execute(f"select count(*) from meta.{meta}").fetchone()[0] >= 1
    con.close()
    write_table(lake, "bronze", "stg_obs", {"dico": ["0101"] * 7, "value": [0.0] * 7})  # lake changes after the build
    con = duckdb.connect(str(out), read_only=True)
    assert con.execute("select count(*) from bronze.stg_obs").fetchone()[0] == 7  # views follow the lake
    con.close()
    again = build_catalog(load_model(manifest), lake_root=lake, manifests_root=manifests, output=out)
    assert again.tables == result.tables  # regenerating replaces the previous file
