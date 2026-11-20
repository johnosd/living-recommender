"""Fronteira pública da coleta; stub entregue pelo sdd-plan da spec 008."""

import json
from collections.abc import Callable
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from pipelines.collectors.wikipedia.catalog import wikipedia_source
from pipelines.collectors.wikipedia.fetch import PendingFetch, SourceBlocked
from pipelines.collectors.wikipedia.identity import (
    validate_associations,
    validate_documents,
)
from pipelines.collectors.wikipedia.manifest import (
    digest,
    encode,
    manifest_key,
    read_manifests,
    validate_run_id,
    verify_file,
)
from pipelines.collectors.wikipedia.state import (
    SUCCESS,
    fingerprint,
    indexes,
    store_roles,
)


class WikipediaError(ValueError):
    """Configuração, identidade, revisão ou conteúdo Wikipedia não utilizável."""


def collect_wikipedia(
    catalog: dict[str, Any],
    *,
    municipalities: list[dict[str, Any]],
    associations: list[dict[str, Any]],
    territory_hash: str,
    storage: Any,
    fetcher: Callable[[dict[str, Any]], dict[str, bytes]],
    run_id: str,
    collected_at_utc: str,
    work_dir: Path,
    resume_manifest: dict[str, Any] | None = None,
    max_municipalities: int | None = None,
    context_checker: Callable[[], bool] | None = None,
    should_stop: Callable[[], bool] | None = None,
    now_utc: Callable[[], str] | None = None,
) -> dict[str, Any]:
    """Coleta com snapshots congelados; fetcher retorna metadata/content JSON brutos.

    Retorna status, manifest_key e entries por DICO; não consulta rede diretamente.
    Contrato completo em 008-ingestao-wikipedia/contracts/wikipedia-cli.md.
    """
    validate_run_id(run_id)
    source = wikipedia_source(catalog)
    territory, mapping = deepcopy(municipalities), deepcopy(associations)
    validate_associations(territory, mapping, source["expected_municipalities"])
    if max_municipalities is not None and (type(max_municipalities) is not int or max_municipalities < 1):
        raise WikipediaError("limite deve ser inteiro positivo")
    if resume_manifest and max_municipalities is not None:
        raise WikipediaError("resume não combina com limite")
    manifests = read_manifests(storage)
    if any(m["run_id"] == run_id for m in manifests):
        raise WikipediaError("run_id já existe")
    previous, _ = indexes(manifests)
    context = {"catalog_snapshot": source, "territory_snapshot": territory,
               "territory_hash": territory_hash, "associations_snapshot": mapping,
               "association_set_hash": digest(mapping)}
    resumed = {}
    if resume_manifest:
        if any(resume_manifest.get(k) != v for k, v in context.items()):
            raise WikipediaError("contexto mudou; iniciar novo ciclo")
        for entry in resume_manifest["entries"]:
            if entry["status"] in SUCCESS:
                for file in entry.get("files", []):
                    verify_file(storage, file)
                resumed[entry["dico"]] = deepcopy(entry)
            elif entry.get("retry_at") and datetime.fromisoformat(collected_at_utc) < datetime.fromisoformat(entry["retry_at"]):
                raise WikipediaError(f"aguardar retry_at={entry['retry_at']}")
    entries, attempted, stopped, stop_reason = [], 0, False, None
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    for association in mapping:
        code = association["dico"]
        if code in resumed:
            entries.append(resumed[code])
            continue
        old = previous.get(code)
        entry = {"dico": code, "status": "pending", "association_hash": digest(association),
                 "scope": association.get("scope"), "files": [], "checked_at_utc": None,
                 "verified_in_run": None, "reason": None, "error": None}
        if old:
            entry["previous_valid_run_id"] = old.get("verified_in_run")
            entry["previous_valid_revision_id"] = old.get("revision_id")
        if should_stop is not None and should_stop():
            stopped, stop_reason = True, "interrupted"
        if stopped or (max_municipalities is not None and attempted >= max_municipalities):
            entry["reason"] = stop_reason or "batch_limit"
            entries.append(entry)
            continue
        attempted += 1
        checked_at = now_utc() if now_utc else collected_at_utc
        entry.update(checked_at_utc=checked_at, verified_in_run=run_id)
        try:
            if association["status"] == "pending_review":
                raise WikipediaError("identity_pending: correspondência não revisada")
            if association["status"] == "absent":
                entry.update(status="absent", reason="no_appropriate_pt_article", absence_evidence=association,
                             fingerprint=digest({"association": association, "territory_hash": territory_hash}))
            else:
                payloads = fetcher(deepcopy(association))
                metadata, parsed = (json.loads(payloads[role]) for role in ("metadata", "content"))
                page, content = validate_documents(association, metadata, parsed)
                signature = fingerprint(metadata, parsed, association, territory_hash)
                same = old and old.get("fingerprint") == signature and old.get("status") != "absent"
                if same:
                    for file in old["files"]:
                        verify_file(storage, file)
                    files = deepcopy(old["files"])
                else:
                    files = store_roles(storage, payloads, old, code, run_id, now_utc() if now_utc else collected_at_utc)
                revision = page["revisions"][0]
                entry.update(status="unchanged" if same else "changed", fingerprint=signature, files=files,
                    page_id=page["pageid"], canonical_title=page["title"], requested_title=association["title"],
                    redirect_chain=metadata.get("query", {}).get("redirects", []), revision_id=revision["revid"],
                    revision_at_utc=revision["timestamp"],
                    permanent_url=f"https://pt.wikipedia.org/w/index.php?oldid={content['revid']}",
                    wikidata_id=page.get("pageprops", {}).get("wikibase_item"),
                    english_url=next((r.get("url") for r in page.get("langlinks", []) if r["lang"] == "en"), None))
            same = old and old.get("fingerprint") == entry.get("fingerprint")
            entry["last_changed_run_id"] = old.get("last_changed_run_id") if same else run_id
        except KeyboardInterrupt:
            entry.update(status="pending", reason="interrupted", error="interrompido pelo operador")
            stopped, stop_reason = True, "interrupted"
        except PendingFetch as error:
            entry.update(status="pending", reason="source_wait", error=str(error), retry_at=error.retry_at)
            stopped, stop_reason = True, "source_wait"
        except SourceBlocked as error:
            entry.update(status="failed", reason="source_blocked", error=str(error))
            stopped, stop_reason = True, "source_blocked"
        except (ValueError, OSError, KeyError, TypeError, IndexError) as error:
            entry.update(status="failed", reason="identity_pending" if association["status"] == "pending_review" else "validation_or_fetch_failed", error=str(error))
        entries.append(entry)
    completed = [e for e in entries if e["status"] in SUCCESS]
    if len(completed) != len(entries):
        status = "partial" if completed else "failed"
    else:
        status = "changed" if any(e["status"] == "changed" or (e["status"] == "absent" and
            previous.get(e["dico"], {}).get("fingerprint") != e["fingerprint"]) for e in entries) else "unchanged"
    result = {"schema_version": 1, "source_id": "wikipedia", "sequence": len(manifests) + 1,
              "run_id": run_id, "cycle_id": resume_manifest["cycle_id"] if resume_manifest else run_id,
              "parent_run_id": resume_manifest["run_id"] if resume_manifest else None,
              "checked_at_utc": collected_at_utc, "status": status,
              **{k: source[k] for k in ("language", "license_id", "license_url", "attribution")},
              **context, "entries": entries}
    if context_checker is not None and not context_checker():
        result.update(status="failed", input_errors=["dependências físicas alteradas durante a coleta"])
    key = manifest_key(run_id)
    storage.put(key, encode(result))
    storage.put(f"reports/wikipedia/collection/{run_id}/summary.json", encode(result))
    return {**result, "manifest_key": key}
