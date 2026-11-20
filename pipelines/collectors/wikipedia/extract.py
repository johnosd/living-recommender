"""Extração editorial sem rede com propriedade única de cada nó textual."""

from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from pipelines.collectors.wikipedia.errors import WikipediaError
from pipelines.collectors.wikipedia.identity import normalized

EXTRACTOR_VERSION = "wikipedia-dom-1"
PRUNE_SELECTORS = "script,style,.mw-editsection,#toc,.toc,.mw-toc,.mw-toc-heading,.navbox,.vertical-navbox,.mw-collapsible-toggle,.mw-jump-link"
STRUCTURAL = {"p", "table", "tr", "td", "th", "caption", "ul", "ol", "li", "dl", "dt", "dd",
              "blockquote", "pre", "figure", "figcaption", "hr"}
INLINE = {"a", "abbr", "b", "bdi", "bdo", "big", "br", "cite", "code", "del", "em", "font", "i",
          "img", "ins", "kbd", "mark", "q", "rp", "rt", "ruby", "s", "samp", "small", "span", "strong",
          "sub", "sup", "time", "tt", "u", "var", "wbr", "noscript"}
WRAPPERS = {"div", "section", "article", "aside", "center", "tbody", "thead", "tfoot", "colgroup", "col"}
HEADINGS = {f"h{n}" for n in range(1, 7)}
NON_NARRATIVE = {"hatnote", "ambox", "ombox", "imbox", "tmbox", "fmbox", "coordinates", "shortdescription"}


def extract_article(metadata: dict, parsed: dict) -> dict:
    """Valida a entrada pública e preserva o diagnóstico como WikipediaError."""
    try:
        return _extract_article(metadata, parsed)
    except (ValueError, KeyError, TypeError, IndexError) as error:
        raise WikipediaError(str(error)) from error


def _extract_article(metadata: dict, parsed: dict) -> dict:
    page = metadata["query"]["pages"][0]
    content = parsed["parse"]
    if page["pageid"] != content["pageid"] or page["revisions"][0]["revid"] != content["revid"]:
        raise ValueError("identidade/revisão incoerente na extração")
    html = content["text"]
    if isinstance(html, dict):
        html = html["*"]
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one(".mw-parser-output")
    if root is None:
        raise ValueError("raiz editorial ausente")
    excluded = []
    for tag in list(root.select(PRUNE_SELECTORS)):
        if not tag.decomposed:
            excluded.append({"tag": tag.name, "text_nodes": len(list(tag.strings))})
            tag.decompose()
    for tag in root.find_all(True):
        if tag.name not in STRUCTURAL | INLINE | WRAPPERS | HEADINGS and tag.get_text(strip=True):
            raise ValueError(f"nó substantivo não suportado: {tag.name}")
    index = content.get("tocdata", {}).get("sections", content.get("sections", []))
    expected = [(s["anchor"], int(s.get("hLevel", s.get("level", 2)))) for s in index]
    actual = [(h.get("id"), int(h.name[1])) for h in root.find_all(list(HEADINGS))]
    if actual != expected:
        raise ValueError(f"índice/headings incoerentes: {actual!r} != {expected!r}")
    for heading, section in zip(root.find_all(list(HEADINGS)), index, strict=True):
        if "line" in section and normalized(heading.get_text()) != normalized(BeautifulSoup(section["line"], "html.parser").get_text()):
            raise ValueError("título de seção divergente do índice")
    sections = [{"section_id": "lead", "parent_section_id": None, "order": 0,
                 "title": "", "level": 0, "anchor": None, "empty": True}]
    blocks, owned, linear, introduction = [], set(), [], []
    current, stack, heading_position = "lead", [], 0

    def new_block(kind, parent, tag=None):
        block = {"block_id": f"b{len(blocks) + 1:06}", "parent_block_id": parent,
                 "section_id": current, "order": len(blocks), "kind": kind, "text": None, "links": [],
                 "context": {key: tag.get(key) for key in ("id", "class", "colspan", "rowspan", "scope")
                             if tag is not None and tag.has_attr(key)}}
        blocks.append(block)
        return block

    def mark_text(node):
        if id(node) in owned:
            raise ValueError("texto atribuído a mais de um bloco")
        owned.add(id(node))
        return str(node)

    def walk_children(node, parent=None, narrative=True, leaf_parent=True):
        nonlocal current, stack, heading_position
        buffer, links = [], []
        parent_block = next((b for b in reversed(blocks) if b["block_id"] == parent), None)
        has_children = False

        def flush(final=False):
            nonlocal buffer, links, has_children
            text = normalized("".join(buffer))
            if text:
                if final and leaf_parent and parent_block is not None and not has_children:
                    block = parent_block
                else:
                    block = new_block("text", parent)
                    has_children = True
                block.update(text=text, links=links)
                linear.append(text)
                if current == "lead" and narrative:
                    introduction.append(text)
            buffer, links = [], []

        def inline(child):
            if isinstance(child, Comment):
                return
            if isinstance(child, NavigableString):
                buffer.append(mark_text(child))
                return
            if child.name == "br":
                buffer.append("\n")
            if child.name == "a" and child.get("href"):
                href = child["href"]
                resolved = urljoin(page.get("fullurl", "https://pt.wikipedia.org/"), href)
                safe = urlsplit(resolved).scheme in {"http", "https"}
                links.append({"href": href, "text": normalized(child.get_text()),
                              "url": resolved if safe else None,
                              "kind": "reference" if href.startswith("#") else ("link" if safe else "unsafe")})
            for descendant in child.children:
                inline(descendant)

        for child in node.children:
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                buffer.append(mark_text(child))
                continue
            if not isinstance(child, Tag):
                continue
            if child.name in HEADINGS:
                flush()
                for text in child.strings:
                    mark_text(text)
                title = normalized(child.get_text())
                level = int(child.name[1])
                while stack and stack[-1]["level"] >= level:
                    stack.pop()
                current = f"s{heading_position + 1:04}"
                section = {"section_id": current, "parent_section_id": stack[-1]["section_id"] if stack else None,
                           "order": heading_position + 1, "title": title, "level": level,
                           "anchor": child.get("id"), "empty": True}
                sections.append(section)
                stack.append(section)
                heading_position += 1
                linear.append(title)
            elif child.name in STRUCTURAL:
                flush()
                block = new_block(child.name, parent, child)
                has_children = True
                walk_children(child, block["block_id"], narrative and child.name not in {"table", "figure"})
            elif child.name in INLINE and not child.find(list(STRUCTURAL | HEADINGS)):
                inline(child)
            else:
                flush()
                has_children = True
                walk_children(child, parent, narrative and not (set(child.get("class", [])) & NON_NARRATIVE), leaf_parent=False)
        flush(final=True)

    walk_children(root)
    remaining = {id(n) for n in root.descendants if isinstance(n, NavigableString)
                 and not isinstance(n, Comment) and str(n).strip()}
    if not remaining <= owned:
        raise ValueError("perda de nós textuais na extração")
    if not any(normalized(str(n)) for n in root.strings):
        raise ValueError("corpo editorial vazio")
    populated = {b["section_id"] for b in blocks if b["text"]}
    for section in sections:
        section["empty"] = section["section_id"] not in populated
    return {"page_id": page["pageid"], "revision_id": content["revid"],
            "wikidata_id": page.get("pageprops", {}).get("wikibase_item"),
            "english_url": next((r.get("url") for r in page.get("langlinks", []) if r["lang"] == "en"), None),
            "introduction": "\n\n".join(introduction), "full_text": "\n\n".join(linear),
            "sections": sections, "blocks": blocks, "extraction_complete": True,
            "audit": {"text_nodes": len(remaining), "owned_text_nodes": len(remaining & owned),
                      "headings": len(actual), "excluded": excluded, "extractor_version": EXTRACTOR_VERSION}}
