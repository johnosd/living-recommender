"""`render_markdown`, `load_sources_info` e a CLI `model_docs` (spec 010, T003 a T005)."""
import json
import re

from pipelines.cli import model_docs as cli
from pipelines.modeldocs.model import load_model
from pipelines.modeldocs.render import load_sources_info, render_markdown
from tests.fixtures.modeldocs.manifests import ROOT, column, make_manifest, model

SOURCES = {"caop": {"license_id": "CC-BY-4.0", "attribution": None},
           "google_distances": {"license_id": "google-terms", "attribution": "Powered by | Google"}}


def render(manifest, sources=SOURCES):
    return render_markdown(load_model(manifest), sources)


def section(document, title):
    return re.split(r"^### ", document, flags=re.MULTILINE)[[p.split("\n")[0] for p in re.split(
        r"^### ", document, flags=re.MULTILINE)].index(title)]


def test_sources_info_reads_the_licenses_of_the_real_catalog():
    info = load_sources_info(ROOT / "config" / "sources.yml")
    assert info["caop"]["license_id"] and "google_distances" in info
    assert info["google_distances"]["attribution"]


def test_each_source_shows_license_attribution_or_that_it_is_unknown():
    manifest = make_manifest([model("a", source_ids=["caop", "google_distances", "ghost"]), model("b")])
    document = render(manifest)
    assert 'caop (CC-BY-4.0); google_distances (google-terms) — atribuição: "Powered by &#124; Google"; ' \
           "ghost (licença não declarada)" in document
    assert "- Fontes: não declaradas" in section(document, "b")


def test_a_table_without_description_or_columns_says_so_and_a_report_carries_the_note():
    manifest = make_manifest([model("rpt_x"), model("main_table", description="Principal.", columns=[column("c")])])
    document = render(manifest)
    assert "- Descrição: sem descrição" in section(document, "rpt_x")
    assert "Colunas declaradas: nenhuma." in section(document, "rpt_x")
    assert "Observação: as colunas listadas são só as declaradas" in section(document, "rpt_x")
    assert "Observação" not in section(document, "main_table")
    assert "| c | n/d | sem descrição | — |" in section(document, "main_table")


def test_coverage_rounds_half_up_and_shows_nd_when_there_is_nothing_to_count():
    half = make_manifest([model(f"t{i}", description="x" if i == 0 else "") for i in range(8)])
    assert "1/8 (13%)" in render(half)  # 12.5 -> 13
    empty = render(make_manifest([model("only_bronze", layer="bronze", description="d")]))
    assert "| silver | n/d | n/d |" in empty


def test_the_diagram_lists_one_edge_per_relationship_and_each_attribute_once():
    manifest = make_manifest(
        [model("dim_x", layer="silver", columns=[column("dico", data_type="VARCHAR(10)")]),
         model("a", columns=[column("dico"), column("alt")]), model("b", columns=[column("dico")])],
        relationships=[("a", "dico", "ref:dim_x", "dico"), ("a", "alt", "ref:dim_x", "dico"),
                       ("b", "dico", "ref:dim_x", "dico")])
    diagram = render(manifest).split("```mermaid")[1].split("```")[0]
    assert diagram.count("}o--||") == 3
    assert diagram.count("dim_x {") == 1 and diagram.count("varchar_10_ dico") == 1
    assert "n_d alt" in diagram


def test_nothing_to_list_prints_none_and_the_document_ends_with_one_newline():
    manifest = make_manifest([model("t", description="d", columns=[column("c", description="d")])])
    document = render(manifest)
    assert "### Sem descrição\n\nNenhuma.\n" in document
    assert document.endswith("\n") and not document.endswith("\n\n")


def test_relationships_appear_only_in_the_origin_table():
    manifest = make_manifest([model("dim_x", columns=[column("dico")]), model("a", columns=[column("dico")])],
                             relationships=[("a", "dico", "ref:dim_x", "dico")])
    document = render(manifest)
    assert "- `dico` -> `dim_x.dico`" in section(document, "a")
    assert "Relacionamentos:" not in section(document, "dim_x")


def test_the_cli_generates_and_reports_the_counts_from_a_manifest_file(tmp_path, capsys):
    manifest = make_manifest([model("a", columns=[column("c")])])
    path, output = tmp_path / "manifest.json", tmp_path / "doc" / "modelo.md"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert cli.main(["--manifest", str(path), "--output", str(output)]) == 0
    assert "1 tabelas, 0 relacionamentos" in capsys.readouterr().out
    assert output.read_text(encoding="utf-8").startswith("# Modelo de dados\n")


def test_the_cli_exits_with_1_on_an_inconsistent_manifest_and_2_when_the_manifest_is_unreadable(tmp_path, capsys):
    bad = make_manifest([model("fact_a", columns=[column("dico")])],
                        relationships=[("fact_a", "dico", "source:ext.ghost", "dico")], sources=["ext.ghost"])
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    assert cli.main(["--manifest", str(path), "--output", str(tmp_path / "x.md")]) == 1
    assert "ghost" in capsys.readouterr().err
    assert cli.main(["--manifest", str(tmp_path / "missing.json"), "--output", str(tmp_path / "x.md")]) == 2
