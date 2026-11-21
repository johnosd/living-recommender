"""Correspondências curatoriais: nomes e QIDs isolados não provam município."""

import csv
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

FIELDS = ("dico", "status", "page_id", "title", "expected_wikidata_id", "scope",
          "evidence_quote", "evidence_url", "evidence_note", "reviewed_at_utc", "reviewer")
SCOPES = {"municipality", "municipality_and_seat"}


def normalized(text):
    return " ".join(unicodedata.normalize("NFKC", text).split())


def evidence_text(html):
    """Normaliza espaços de markup/citações sem apagar palavras da evidência."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select("script,style,.reference,.mw-editsection,#toc,.toc,.navbox,.vertical-navbox"):
        if not tag.decomposed:
            tag.decompose()
    text = normalized(soup.get_text(" ", strip=True))
    return evidence_spacing(text)


def evidence_spacing(text):
    return re.sub(r"([(\[])\s+", r"\1", re.sub(r"\s+([,.;:!?%)\]])", r"\1", text))


def evidence_valid(row):
    try:
        timestamp = datetime.fromisoformat(row["reviewed_at_utc"])
        url = urlsplit(row["evidence_url"])
        return bool(timestamp.tzinfo and row["reviewer"].strip() and row["evidence_note"].strip()
                    and url.scheme == "https" and url.hostname == "pt.wikipedia.org"
                    and not url.username)
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def validate_associations(municipalities, associations, expected):
    codes = [r.get("dico") for r in municipalities]
    mapped = [r.get("dico") for r in associations]
    if (len(codes) != expected or len(set(codes)) != len(codes)
            or any(not isinstance(c, str) or not re.fullmatch(r"\d{4}", c) for c in codes)):
        raise ValueError("dimensão municipal inválida ou universo divergente")
    if any(not r.get("official_name") or not r.get("caop_version") for r in municipalities):
        raise ValueError("dimensão sem nome/versão")
    if len(set(mapped)) != len(mapped) or set(mapped) != set(codes):
        raise ValueError("correspondências duplicadas, extras ou perdidas")
    pages = []
    for row in associations:
        status = row.get("status")
        if status not in {"validated", "absent", "pending_review"}:
            raise ValueError("status curatorial inválido")
        if status != "pending_review" and not evidence_valid(row):
            raise ValueError(f"evidência insuficiente: {row['dico']}")
        if status == "validated":
            if (type(row.get("page_id")) is not int or row["page_id"] < 1 or not row.get("title")
                    or row.get("scope") not in SCOPES or not row.get("evidence_quote", "").strip()):
                raise ValueError(f"identidade/abrangência inválida: {row['dico']}")
            qid = row.get("expected_wikidata_id")
            if qid and not re.fullmatch(r"Q[1-9]\d*", qid):
                raise ValueError("QID inválido")
            pages.append(row["page_id"])
        elif status == "absent" and (row.get("page_id") or row.get("title")):
            raise ValueError("ausência não pode apontar artigo aceito")
    if len(pages) != len(set(pages)):
        raise ValueError("mesmo artigo associado a municípios distintos")


def load_associations(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise ValueError("schema de correspondências inválido")
        rows = list(reader)
    for row in rows:
        row["page_id"] = int(row["page_id"]) if row["page_id"] else None
    return rows


def validate_documents(association, metadata, parsed):
    if not isinstance(metadata, dict) or not isinstance(parsed, dict):
        raise TypeError("documentos JSON devem ser objetos")
    if "error" in metadata or "error" in parsed:
        raise ValueError("erro da API no corpo JSON")
    query = metadata.get("query")
    if not isinstance(query, dict):
        raise TypeError("query inválida")
    pages = query.get("pages", [])
    if not isinstance(pages, list) or len(pages) != 1 or not isinstance(pages[0], dict):
        raise ValueError("resposta não resolve exatamente um artigo")
    page = pages[0]
    props = page.get("pageprops", {})
    if not isinstance(props, dict):
        raise TypeError("pageprops inválido")
    if (page.get("missing") is not None or page.get("invalid") is not None
            or page.get("pageid") != association["page_id"] or page.get("ns") != 0
            or "disambiguation" in props):
        raise ValueError("identidade incorreta, inexistente ou desambiguação")
    if association.get("expected_wikidata_id") and props.get("wikibase_item") != association["expected_wikidata_id"]:
        raise ValueError("QID divergente da curadoria")
    revisions = page.get("revisions", [])
    content = parsed.get("parse", {})
    if not isinstance(content, dict):
        raise TypeError("parse inválido")
    if (not isinstance(revisions, list) or len(revisions) != 1 or not isinstance(revisions[0], dict)
            or not isinstance(revisions[0].get("revid"), int)
            or not revisions[0].get("timestamp")
            or content.get("revid") != revisions[0]["revid"]
            or content.get("pageid") != page["pageid"]
            or content.get("title") != page.get("title")):
        raise ValueError("revisão/identidade do parse incoerente")
    html = content.get("text")
    if isinstance(html, dict):
        html = html.get("*")
    if not isinstance(html, str) or not html.strip():
        raise ValueError("conteúdo ausente")
    text = evidence_text(html)
    quote = evidence_spacing(normalized(association["evidence_quote"]))
    if quote not in text:
        raise ValueError("evidência de abrangência removida; requer revisão")
    return page, content
