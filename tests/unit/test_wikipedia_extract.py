from copy import deepcopy

import pytest

from pipelines.collectors.wikipedia.extract import extract_article
from pipelines.collectors.wikipedia.handler import WikipediaError
from tests.fixtures.wikipedia.responses import documents


def article(html, sections=()):
    meta, parsed = documents(text='<div class="mw-parser-output">' + html + '</div>')
    parsed["parse"].pop("sections")
    parsed["parse"]["tocdata"] = {"sections": list(sections)}
    return extract_article(meta, parsed)


def test_wikipedia_current_toc_wrappers_empty_and_duplicate_titles():
    index = [{"index": str(i), "anchor": anchor, "line": "Mesmo", "hLevel": level}
             for i, anchor, level in [(1, "A", 2), (2, "B", 3), (3, "C", 2)]]
    result = article('<div id="toc"><h2>Índice</h2>controle</div><p>Lead <b>com</b> texto.</p>'
        '<div class="mw-heading"><h2 id="A">Mesmo</h2><span class="mw-editsection">editar</span></div>'
        '<h3 id="B">Mesmo</h3><p>Filho</p><h2 id="C">Mesmo</h2>', index)
    assert result["introduction"] == "Lead com texto."
    _lead, a, b, c = result["sections"]
    assert a["empty"] and c["empty"] and not b["empty"]
    assert b["parent_section_id"] == a["section_id"]
    assert c["parent_section_id"] is None
    assert result["audit"]["text_nodes"] == result["audit"]["owned_text_nodes"]


def test_wikipedia_table_direct_rows_context_and_generic_fragments():
    result = article('<table class="infobox"><tr><td rowspan="2"><div>A</div><div>B</div>'
        '<table><tr><th scope="row">C</th></tr></table>D</td></tr></table><p>Narrativa.</p>')
    assert result["introduction"] == "Narrativa."
    leaves = [b["text"] for b in result["blocks"] if b["text"]]
    assert leaves == ["A", "B", "C", "D", "Narrativa."]
    assert any(b["context"].get("rowspan") == "2" for b in result["blocks"])
    for table in (b for b in result["blocks"] if b["kind"] == "table"):
        assert table["text"] is None


def test_wikipedia_inline_whitespace_nested_lists_references_and_unsafe_links():
    result = article('<p>Um <em>texto</em> com&nbsp;espaços <a href="javascript:alert(1)">link</a>.</p>'
        '<ul><li>Item<ul><li>Subitem <a href="#ref">[1]</a></li></ul>Fim</li></ul>'
        '<p id="ref">Referência <a href="/wiki/Portugal">Portugal</a>.</p>')
    assert result["full_text"].count("Subitem") == 1
    assert "Um texto com espaços link." in result["full_text"]
    links = [link for b in result["blocks"] for link in b["links"]]
    assert links[0]["url"] is None and links[0]["kind"] == "unsafe"
    assert links[-1]["url"] == "https://pt.wikipedia.org/wiki/Portugal"


@pytest.mark.parametrize("html,index", [('<p>x</p><h2 id="missing">Título</h2>', []),
    ('<p>x</p>', [{"anchor": "missing", "hLevel": 2}]), ('<mystery>Perdido</mystery>', []), ('', [])])
def test_wikipedia_loss_or_unknown_substantive_content_rejected(html, index):
    with pytest.raises(ValueError):
        article(html, index)


def test_wikipedia_complete_article_without_introduction_is_honest():
    result = article('<h2 id="A">Dados</h2><table><tr><td>Conteúdo</td></tr></table>',
                     [{"anchor": "A", "hLevel": 2}])
    assert not result["introduction"] and result["extraction_complete"]


def test_wikipedia_hatnote_preserved_but_not_narrative_intro_and_title_mismatch_fails():
    result = article('<div class="hatnote">Nota: outra entidade.</div><p>Introdução original.</p>')
    assert result["introduction"] == "Introdução original."
    assert "Nota: outra entidade." in result["full_text"]
    with pytest.raises(ValueError, match="título"):
        article('<h2 id="A">Saúde</h2><p>Texto</p>', [{"anchor": "A", "hLevel": 2, "line": "Religiões"}])


def test_wikipedia_does_not_modify_documents():
    meta, parsed = documents()
    original = deepcopy((meta, parsed))
    extract_article(meta, parsed)
    assert original == (meta, parsed)


@pytest.mark.parametrize("case,message", [("revision", "revisão"), ("root", "raiz"),
    ("index", "índice"), ("unsupported", "não suportado"), ("missing_field", "parse")])
def test_wikipedia_public_extraction_errors_are_catchable_by_documented_type(case, message):
    meta, parsed = documents()
    if case == "revision":
        parsed["parse"]["revid"] = -1
    elif case == "root":
        parsed["parse"]["text"] = "<p>Sem raiz editorial.</p>"
    elif case == "index":
        parsed["parse"]["sections"] = []
    elif case == "unsupported":
        parsed["parse"]["text"] = '<div class="mw-parser-output"><mystery>Texto substantivo</mystery></div>'
        parsed["parse"]["sections"] = []
    else:
        parsed.pop("parse")
    with pytest.raises(WikipediaError, match=message) as captured:
        extract_article(meta, parsed)
    assert isinstance(captured.value, ValueError)
