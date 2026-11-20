"""Preparação offline rastreável; schemas explícitos inclusive sem artigos."""

import csv
import json
import platform
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from pipelines.collectors.wikipedia.catalog import wikipedia_source
from pipelines.collectors.wikipedia.coverage import assess_wikipedia_coverage
from pipelines.collectors.wikipedia.extract import EXTRACTOR_VERSION, extract_article
from pipelines.collectors.wikipedia.identity import (
    validate_associations,
    validate_documents,
)
from pipelines.collectors.wikipedia.local import dependency_hashes, file_hash
from pipelines.collectors.wikipedia.manifest import (
    digest,
    encode,
    validate_run_id,
    verify_file,
)
from pipelines.collectors.wikipedia.state import fingerprint

SCHEMA_VERSION = "wikipedia-parquet-1"
TABLES = {"wikipedia_revision": "bronze", "wikipedia_article": "silver", "wikipedia_section": "silver",
          "wikipedia_block": "silver", "wikipedia_coverage": "silver"}


def schema(strings=(), integers=(), booleans=()):
    return pa.schema([(n, pa.string()) for n in strings] + [(n, pa.int64()) for n in integers]
                     + [(n, pa.bool_()) for n in booleans])


SCHEMAS = {
    "wikipedia_revision": schema(("dico", "scope", "canonical_title", "fingerprint", "association_hash",
        "territory_hash", "source_run_id", "checked_at_utc", "revision_at_utc", "permanent_url",
        "metadata_raw_key", "metadata_raw_sha256", "content_raw_key", "content_raw_sha256",
        "metadata_raw_collected_at_utc", "content_raw_collected_at_utc", "manifest_key", "processing_signature"),
        ("page_id", "revision_id")),
    "wikipedia_article": schema(("dico", "scope", "canonical_title", "introduction", "full_text", "wikidata_id",
        "english_url", "permanent_url", "history_url", "revision_at_utc", "metadata_observed_at_utc", "license_id",
        "license_url", "attribution", "normalization", "processing_signature", "audit_json", "processed_at_utc"), ("page_id", "revision_id")),
    "wikipedia_section": schema(("dico", "section_id", "parent_section_id", "title", "anchor", "processing_signature"),
        ("section_order", "level"), ("empty",)),
    "wikipedia_block": schema(("dico", "block_id", "section_id", "parent_block_id", "kind", "text", "links_json",
        "context_json", "processing_signature"), ("block_order",)),
    "wikipedia_coverage": schema(("dico", "status", "reason", "error", "absence_evidence_json", "checked_at_utc",
        "source_run_id", "processing_signature", "canonical_title", "scope", "permanent_url", "revision_at_utc",
        "wikidata_id", "english_url"), ("page_id", "revision_id", "previous_valid_revision_id", "section_count", "block_count",
        "introduction_characters", "full_text_characters"),
        ("identity_validated", "extraction_complete", "has_introduction", "has_wikidata", "has_english")),
}


def transformation_dependencies():
    directory = Path(__file__).parent
    repo = directory.parents[2]
    code_paths = [*directory.glob("*.py"), *sorted((repo / "analytics/dbt/models/wikipedia").glob("*")),
                  *sorted((repo / "analytics/dbt/tests").glob("wikipedia*.sql"))]
    return dependency_hashes(p for p in code_paths if p.is_file())


def processing_signature(manifest, dependencies=None):
    repo = Path(__file__).resolve().parents[3]
    code = {Path(p).relative_to(repo).as_posix(): h for p, h in (dependencies or transformation_dependencies()).items()}
    return digest({"entries": sorted((e["dico"], e.get("fingerprint")) for e in manifest["entries"]),
        "territory_hash": manifest["territory_hash"], "association_set_hash": manifest["association_set_hash"],
        "catalog": manifest["catalog_snapshot"], "extractor": EXTRACTOR_VERSION, "schema": SCHEMA_VERSION,
        "parser": "html.parser", "python": platform.python_version(), "bs4": version("beautifulsoup4"), "code": code})


def write_csv(path, rows, fields):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def prepare_wikipedia(storage, manifest, candidate, dimension_path):
    candidate = Path(candidate)
    prepared = candidate / "prepared"
    reports = candidate / "lake/silver/wikipedia_reports"
    prepared.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    source = wikipedia_source({"sources": {"wikipedia": manifest["catalog_snapshot"]}})
    municipalities = manifest["territory_snapshot"]
    mapping = manifest["associations_snapshot"]
    validate_associations(municipalities, mapping, source["expected_municipalities"])
    if manifest["association_set_hash"] != digest(mapping):
        raise ValueError("hash das associações divergente")
    if file_hash(dimension_path) != manifest["territory_hash"]:
        raise ValueError("dimensão física divergente da coleta")
    current = pd.read_parquet(dimension_path)[["dico", "official_name", "caop_version"]].to_dict("records")
    if current != municipalities:
        raise ValueError("snapshot territorial divergente")
    code_dependencies = transformation_dependencies()
    signature = processing_signature(manifest, code_dependencies)
    processed_at_utc = datetime.now(UTC).isoformat(timespec="seconds")
    rows = {table: [] for table in TABLES}
    coverage, inputs = [], list(manifest.get("input_errors", []))
    if manifest["status"] not in {"changed", "unchanged"}:
        inputs.append(f"tentativa incompleta: {manifest['status']}")
    by_code = {a["dico"]: a for a in mapping}
    dependencies = {**code_dependencies, str(Path(dimension_path).resolve()): manifest["territory_hash"]}
    section_inventory = []
    for entry in manifest["entries"]:
        code = entry["dico"]
        status = entry["status"]
        cov = {**{k: entry.get(k) for k in ("page_id", "canonical_title", "scope", "permanent_url", "revision_at_utc", "wikidata_id", "english_url")},
               "dico": code, "status": status, "identity_validated": False,
               "extraction_complete": False, "has_introduction": False, "section_count": 0, "block_count": 0,
               "introduction_characters": None, "full_text_characters": None,
               "has_wikidata": bool(entry.get("wikidata_id")), "has_english": bool(entry.get("english_url")),
               "reason": entry.get("reason"), "error": entry.get("error"), "revision_id": entry.get("revision_id"),
               "previous_valid_revision_id": entry.get("previous_valid_revision_id"),
               "checked_at_utc": entry.get("checked_at_utc"), "source_run_id": entry.get("verified_in_run"),
               "processing_signature": signature, "absence_evidence": entry.get("absence_evidence")}
        if status == "failed" and entry.get("reason") == "identity_pending":
            cov["status"] = "identity_pending"
        if status == "absent":
            if by_code.get(code, {}).get("status") != "absent" or entry.get("absence_evidence") != by_code.get(code):
                inputs.append(f"{code}: evidência de ausência divergente")
        elif status in {"changed", "unchanged"}:
            try:
                association = by_code[code]
                if entry["association_hash"] != digest(association):
                    raise ValueError("associação divergente")
                files = {f["role"]: f for f in entry["files"]}
                if set(files) != {"metadata", "content"} or len(entry["files"]) != 2:
                    raise ValueError("roles raw inválidos")
                for role, file in files.items():
                    origin = validate_run_id(file["run_id"])
                    if file["key"] != f"raw/source=wikipedia/dico={code}/run_id={origin}/{role}.json":
                        raise ValueError("referência raw fora do município/role")
                    if hasattr(storage, "local_path"):
                        dependencies[str(storage.local_path(file["key"]).resolve())] = file["sha256"]
                metadata, parsed = (json.loads(verify_file(storage, files[r])) for r in ("metadata", "content"))
                page, content = validate_documents(association, metadata, parsed)
                if (entry["fingerprint"] != fingerprint(metadata, parsed, association, manifest["territory_hash"])
                        or entry["revision_id"] != content["revid"] or entry["page_id"] != page["pageid"]):
                    raise ValueError("fingerprint/revisão divergente")
                cov["identity_validated"] = True
                result = extract_article(metadata, parsed)
                cov.update(status="valid", extraction_complete=result["extraction_complete"], reason=None,
                    has_introduction=bool(result["introduction"]), section_count=len(result["sections"]),
                    introduction_characters=len(result["introduction"]), full_text_characters=len(result["full_text"]),
                    block_count=len(result["blocks"]))
                revision = {k: entry.get(k) for k in ("dico", "scope", "canonical_title", "fingerprint", "association_hash",
                    "checked_at_utc", "revision_at_utc", "permanent_url", "page_id", "revision_id")}
                revision.update(territory_hash=manifest["territory_hash"], source_run_id=entry["verified_in_run"],
                    manifest_key=f"manifests/wikipedia/{manifest['run_id']}.json", processing_signature=signature)
                for role, file in files.items():
                    revision.update({f"{role}_raw_key": file["key"], f"{role}_raw_sha256": file["sha256"],
                                     f"{role}_raw_collected_at_utc": file["raw_collected_at_utc"]})
                rows["wikipedia_revision"].append(revision)
                article = {**result, **{k: entry.get(k) for k in ("dico", "scope", "canonical_title", "permanent_url", "revision_at_utc")},
                    **{k: manifest[k] for k in ("license_id", "license_url", "attribution")},
                    "history_url": f"https://pt.wikipedia.org/w/index.php?curid={entry['page_id']}&action=history",
                    "metadata_observed_at_utc": entry["checked_at_utc"], "normalization": EXTRACTOR_VERSION,
                    "processing_signature": signature, "audit_json": encode(result["audit"]).decode(), "processed_at_utc": processed_at_utc}
                rows["wikipedia_article"].append(article)
                for section in result["sections"]:
                    row = {**section, "dico": code, "section_order": section["order"], "processing_signature": signature}
                    rows["wikipedia_section"].append(row)
                    section_inventory.append({**row, "canonical_title": entry["canonical_title"]})
                for block in result["blocks"]:
                    rows["wikipedia_block"].append({**block, "dico": code, "block_order": block["order"],
                        "links_json": encode(block["links"]).decode(), "context_json": encode(block["context"]).decode(),
                        "processing_signature": signature})
            except (ValueError, OSError, KeyError, TypeError, IndexError) as error:
                cov.update(status="extraction_failed" if cov["identity_validated"] else "failed",
                           extraction_complete=False, reason="preparation_failed", error=str(error))
        coverage.append(cov)
    readiness = assess_wikipedia_coverage(municipalities, coverage, input_errors=tuple(inputs))
    for cov in coverage:
        rows["wikipedia_coverage"].append({**cov, "absence_evidence_json": encode(cov["absence_evidence"]).decode()})
    for table, values in rows.items():
        pq.write_table(pa.Table.from_pylist(values, schema=SCHEMAS[table]), prepared / f"{table}.parquet")
    write_csv(reports / "coverage.csv", rows["wikipedia_coverage"], SCHEMAS["wikipedia_coverage"].names)
    write_csv(reports / "sections.csv", section_inventory,
              ("dico", "canonical_title", "section_id", "parent_section_id", "section_order", "level", "title", "anchor", "empty"))
    summary = {"source_id": "wikipedia", "selected_run_id": manifest["run_id"], "processing_signature": signature,
        "parser": f"html.parser/Python {platform.python_version()}", "beautifulsoup4": version("beautifulsoup4"),
        "counts": {table: len(values) for table, values in rows.items()}, "readiness": readiness,
        "section_titles": sorted({s["title"] for s in section_inventory if s["title"]}),
        "license_id": manifest["license_id"], "attribution": manifest["attribution"], "processed_at_utc": processed_at_utc}
    (reports / "readiness.json").write_bytes(encode(readiness))
    (reports / "summary.json").write_bytes(encode(summary))
    if readiness["ready"] and dependency_hashes(dependencies) != dependencies:
        raise ValueError("dependências alteradas durante o preparo")
    return {**summary, "dependencies": dependencies}
