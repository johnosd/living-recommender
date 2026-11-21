"""Fixtures públicas travadas da spec 008; exemplos sintéticos, sem rede."""

import json
from copy import deepcopy

HTML = """<div class="mw-parser-output">
<p>Alfa é um município português. Conheça <a href="/wiki/Portugal">Portugal</a>.</p>
<div class="mw-heading mw-heading2"><h2 id="Populacao">População</h2>
<span class="mw-editsection">editar</span></div>
<table class="wikitable"><caption>Censos locais</caption><tbody><tr>
<th>Município</th><td>Alfa<table><tr><td>Freguesia Beta</td></tr></table></td>
</tr></tbody></table>
<div class="mw-heading mw-heading2"><h2 id="Religioes">Religiões</h2></div>
<p>Parágrafo de religião.</p>
<div class="mw-heading mw-heading2"><h2 id="Saude">Saúde</h2></div>
<p>Primeiro parágrafo de saúde.</p><p>Segundo parágrafo de saúde.</p>
<ul><li>Hospital Alfa</li><li>Centro Beta</li></ul>
<p>Fonte <sup class="reference"><a href="#cite_note-1">[1]</a></sup>.</p>
<h2 id="Referencias">Referências</h2>
<ol class="references"><li id="cite_note-1"><a href="https://example.test/fonte">Fonte local</a></li></ol>
</div>"""


def catalog(count=2):
    return {"sources": {"wikipedia": {
        "id": "wikipedia", "publisher": "Wikipedia em português",
        "responsible_party": "living-recommender", "license_id": "CC-BY-SA-4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "attribution": "Contribuidores da Wikipedia", "language": "pt",
        "api_url": "https://pt.wikipedia.org/w/api.php",
        "collection_method": "api_json", "frequency": "monthly",
        "territorial_level": "municipality", "expected_municipalities": count,
        "robots_exception": "008-R-001-authorized-2026-11-20",
        "maxlag": 5, "min_interval_seconds": 1.0,
    }}}


def municipalities():
    return [
        {"dico": "0001", "official_name": "Alfa", "caop_version": "2025"},
        {"dico": "0002", "official_name": "Beta", "caop_version": "2025"},
    ]


def associations():
    return [{
        "dico": code, "status": "validated", "page_id": page_id,
        "title": name, "expected_wikidata_id": f"Q{page_id}",
        "scope": "municipality", "evidence_quote": f"{name} é um município português.",
        "evidence_url": f"https://pt.wikipedia.org/w/index.php?oldid={page_id * 10}",
        "evidence_note": "Município distinto de sede, homônimos e outros países.",
        "reviewed_at_utc": "2026-11-20T09:00:00Z", "reviewer": "fixture",
    } for code, page_id, name in (("0001", 101, "Alfa"), ("0002", 102, "Beta"))]


def documents(association=None, *, revision=1001, text=None):
    a = association or associations()[0]
    page_id, title = a["page_id"], a["title"]
    metadata = {"batchcomplete": True, "query": {"pages": [{
        "pageid": page_id, "ns": 0, "title": title,
        "fullurl": f"https://pt.wikipedia.org/wiki/{title}",
        "pageprops": {"wikibase_item": a["expected_wikidata_id"]},
        "revisions": [{"revid": revision, "timestamp": "2026-11-19T12:00:00Z"}],
        "langlinks": [{"lang": "en", "title": title,
                       "url": f"https://en.wikipedia.org/wiki/{title}"}],
    }]}}
    html = text if text is not None else HTML.replace("Alfa", title)
    parsed = {"parse": {"title": title, "pageid": page_id, "revid": revision,
        "text": html, "properties": {"wikibase_item": a["expected_wikidata_id"]},
        "sections": [{"index": str(i), "anchor": anchor, "line": title_, "level": "2"}
                     for i, (anchor, title_) in enumerate([
                         ("Populacao", "População"), ("Religioes", "Religiões"),
                         ("Saude", "Saúde"), ("Referencias", "Referências"),
                     ], 1)],
    }}
    return metadata, parsed


def encode(document):
    return json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def fetcher(*, overrides=None, failures=(), on_fetch=None):
    """Colaborador injetado: responses são documentos públicos da API, não da unidade."""
    calls = []

    def fetch(association):
        calls.append(deepcopy(association))
        if on_fetch is not None:
            on_fetch(association)
        if association["dico"] in failures:
            raise OSError("temporary network failure")
        meta, parsed = documents(association)
        if overrides and association["dico"] in overrides:
            meta, parsed = deepcopy(overrides[association["dico"]])
        return {"metadata": encode(meta), "content": encode(parsed)}

    return fetch, calls
