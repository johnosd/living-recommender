"""Manifest Wikipedia independente do contrato genérico de indicadores."""

import hashlib
import json
import re


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else encode(value)).hexdigest()


def validate_run_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,100}", value):
        raise ValueError("run_id inválido")
    return value


def manifest_key(run_id):
    return f"manifests/wikipedia/{validate_run_id(run_id)}.json"


def read_manifests(storage):
    if hasattr(storage, "local_path"):
        folder = storage.local_path("manifests/wikipedia")
        keys = [f"manifests/wikipedia/{p.name}" for p in folder.glob("*.json")]
    else:
        keys = [k for k in storage.list_keys() if k.startswith("manifests/wikipedia/") and k.endswith(".json")]
    result = []
    for key in keys:
        document = json.loads(storage.get(key))
        if (document.get("schema_version") != 1 or document.get("source_id") != "wikipedia"
                or manifest_key(document["run_id"]) != key):
            raise ValueError("manifest Wikipedia inválido")
        result.append(document)
    return sorted(result, key=lambda m: (m["sequence"], m["run_id"]))


def verify_file(storage, file):
    payload = storage.get(file["key"])
    if len(payload) != file["bytes"] or digest(payload) != file["sha256"]:
        raise ValueError(f"checksum/bytes divergente: {file['key']}")
    return payload
