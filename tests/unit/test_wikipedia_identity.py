from copy import deepcopy

import pytest

from pipelines.collectors.wikipedia.identity import (
    validate_associations,
    validate_documents,
)
from tests.fixtures.wikipedia.responses import associations, documents, municipalities


def test_wikipedia_valid_mapping():
    validate_associations(municipalities(), associations(), 2)


@pytest.mark.parametrize("case", ["duplicate", "extra", "lost", "seat", "evidence", "same_page"])
def test_wikipedia_mapping_rejections(case):
    rows = associations()
    if case == "duplicate":
        rows.append(deepcopy(rows[0]))
    elif case == "extra":
        rows[0]["dico"] = "9999"
    elif case == "lost":
        rows.pop()
    elif case == "seat":
        rows[0]["scope"] = "seat_only"
    elif case == "evidence":
        rows[0]["evidence_note"] = ""
    else:
        rows[1]["page_id"] = rows[0]["page_id"]
    with pytest.raises(ValueError):
        validate_associations(municipalities(), rows, 2)


def test_wikipedia_absence_requires_documented_review():
    rows = associations()
    rows[0].update(status="absent", page_id=None, title="")
    validate_associations(municipalities(), rows, 2)
    rows[0]["reviewer"] = ""
    with pytest.raises(ValueError):
        validate_associations(municipalities(), rows, 2)


@pytest.mark.parametrize("name", ["Cuba", "Corvo", "Gavião", "Nazaré", "Santa Cruz"])
def test_wikipedia_homonym_identity_and_removed_evidence(name):
    mapping = associations()[0]
    meta, parsed = documents()
    meta["query"]["pages"][0].update(pageid=999, title=name)
    with pytest.raises(ValueError):
        validate_documents(mapping, meta, parsed)
    meta, parsed = documents()
    parsed["parse"]["text"] = "<p>Esta página descreve apenas uma sede.</p>"
    with pytest.raises(ValueError, match="evidência"):
        validate_documents(mapping, meta, parsed)


def test_wikipedia_page_id_survives_title_move():
    mapping = associations()[0]
    meta, parsed = documents()
    meta["query"]["pages"][0]["title"] = parsed["parse"]["title"] = "Alfa (município)"
    assert validate_documents(mapping, meta, parsed)[0]["pageid"] == mapping["page_id"]


def test_wikipedia_evidence_inline_link_punctuation_and_citation_are_not_removed_words():
    mapping = associations()[0]
    mapping["evidence_quote"] = "Município de Alfa, no distrito português."
    meta, parsed = documents(text='<div class="mw-parser-output"><p>Município de <a>Alfa</a>, '
        '<sup class="reference"><a>[1]</a></sup>no distrito <b>português</b>.</p></div>')
    validate_documents(mapping, meta, parsed)
    parsed["parse"]["text"] = parsed["parse"]["text"].replace('no distrito', 'em outro distrito')
    with pytest.raises(ValueError, match="evidência"):
        validate_documents(mapping, meta, parsed)


def test_wikipedia_evidence_parenthesized_inline_label():
    mapping = associations()[0]
    mapping["evidence_quote"] = "Alfa, região (NUTS II) de Portugal."
    meta, parsed = documents(text='<p>Alfa, região (<a>NUTS II</a>) de Portugal.</p>')
    validate_documents(mapping, meta, parsed)
