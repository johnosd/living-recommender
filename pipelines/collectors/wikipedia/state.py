"""Conteúdo válido e tentativas recentes são índices distintos."""

from copy import deepcopy

from pipelines.collectors.wikipedia.manifest import digest, verify_file

SUCCESS = {"changed", "unchanged", "absent"}
# Somente campos operacionais documentados; HTML/revisão nunca são ignorados.
OPERATIONAL_KEYS = {"batchcomplete", "continue", "warnings", "servedby", "curtimestamp", "_http_responses"}


def editorial_document(document):
    return {k: v for k, v in document.items() if k not in OPERATIONAL_KEYS}


def fingerprint(metadata, parsed, association, territory_hash):
    return digest({"metadata": editorial_document(metadata), "content": editorial_document(parsed),
                   "association": association, "territory_hash": territory_hash})


def indexes(manifests):
    valid, latest = {}, {}
    for manifest in manifests:
        for entry in manifest["entries"]:
            latest[entry["dico"]] = deepcopy(entry)
            if entry["status"] in SUCCESS:
                valid[entry["dico"]] = deepcopy(entry)
    return valid, latest


def store_roles(storage, payloads, previous, dico, run_id, collected_at):
    old_roles = {f["role"]: f for f in (previous or {}).get("files", [])}
    files = []
    for role in ("metadata", "content"):
        payload = payloads[role]
        if not isinstance(payload, bytes):
            raise TypeError("fetcher deve devolver bytes")
        old = old_roles.get(role)
        if old:
            verify_file(storage, old)
        if old and old["sha256"] == digest(payload) and old["bytes"] == len(payload):
            files.append(deepcopy(old))
        else:
            key = f"raw/source=wikipedia/dico={dico}/run_id={run_id}/{role}.json"
            storage.put(key, payload)
            files.append({"role": role, "key": key, "sha256": digest(payload), "bytes": len(payload),
                          "run_id": run_id, "raw_collected_at_utc": collected_at})
    return files
