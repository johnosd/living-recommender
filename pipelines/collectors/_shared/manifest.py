"""Manifest versionado e seleção da última coleta completa."""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

from pipelines.collectors._shared.catalog import REGIONS

SCHEMA_VERSION = 1
STATUSES = {"changed", "unchanged", "failed"}


class ManifestError(ValueError):
    """Manifest inválido ou incompleto."""


def file_digest(path: str | Path, *, key: str, region: str) -> dict:
    """Calcula SHA-256 sem carregar o arquivo inteiro em memória."""
    digest = hashlib.sha256()
    size = 0
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return {"region": region, "key": key, "sha256": digest.hexdigest(), "bytes": size}


def make_manifest(
    source: dict,
    *,
    run_id: str,
    collected_at_utc: str,
    status: str,
    files: list[dict] | None = None,
    error: str | None = None,
    previous_changed_run_id: str | None = None,
) -> dict:
    if status not in STATUSES:
        raise ManifestError(f"status desconhecido: {status}")
    if not run_id or "/" in run_id or "\\" in run_id or run_id in (".", ".."):
        raise ManifestError("run_id inválido")
    try:
        parsed = datetime.fromisoformat(collected_at_utc)
    except ValueError as exc:
        raise ManifestError("collected_at_utc inválido") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ManifestError("collected_at_utc deve estar em UTC")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "source_id": source["id"],
        "run_id": run_id,
        "collected_at_utc": collected_at_utc,
        "status": status,
        "version": source["version"],
        "reference_period": source["reference_period"],
        "source_url": dict(source["urls"]),
        "publisher": source.get("publisher"),
        "collection_method": source["collection_method"],
        "license_id": source["license_id"],
        "files": files or [],
        "error": error,
        "previous_changed_run_id": previous_changed_run_id,
    }
    if source.get("source_release_date"):
        manifest["source_release_date"] = source["source_release_date"]
    if status == "changed":
        validate_changed(manifest)
    if status == "failed" and not error:
        raise ManifestError("falha exige mensagem de erro")
    return manifest


def validate_changed(manifest: dict) -> None:
    if manifest.get("status") != "changed" or manifest.get("schema_version") != SCHEMA_VERSION:
        raise ManifestError("manifest changed inválido")
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) != len(REGIONS):
        raise ManifestError("manifest changed exige três arquivos")
    if any(not isinstance(entry, dict) for entry in files):
        raise ManifestError("entrada de arquivo inválida")
    if {entry.get("region") for entry in files} != set(REGIONS):
        raise ManifestError("regiões do manifest incompletas")
    for entry in files:
        if not isinstance(entry.get("key"), str) or not entry["key"].startswith("raw/"):
            raise ManifestError("chave raw inválida")
        if not isinstance(entry.get("sha256"), str) or len(entry["sha256"]) != 64:
            raise ManifestError("checksum inválido")
        if not isinstance(entry.get("bytes"), int) or entry["bytes"] <= 0:
            raise ManifestError("tamanho inválido")


def encode_manifest(manifest: dict) -> bytes:
    return (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def latest_changed(storage, source_id: str = "caop") -> dict | None:
    """Ignora tentativas failed/unchanged e escolhe por horário, depois run_id."""
    prefix = f"manifests/{source_id}/"
    candidates = []
    for key in storage.list_keys():
        if not key.startswith(prefix) or not key.endswith(".json"):
            continue
        try:
            manifest = json.loads(storage.get(key))
        except (ValueError, TypeError) as exc:
            raise ManifestError(f"JSON inválido: {key}") from exc
        if manifest.get("source_id") != source_id or manifest.get("status") != "changed":
            continue
        validate_changed(manifest)
        candidates.append(manifest)
    return (
        max(candidates, key=lambda m: (datetime.fromisoformat(m["collected_at_utc"]), m["run_id"]))
        if candidates
        else None
    )


def same_checksums(files: list[dict], previous: dict | None) -> bool:
    if previous is None:
        return False
    current = {entry["region"]: entry["sha256"] for entry in files}
    prior = {entry["region"]: entry["sha256"] for entry in previous["files"]}
    return current == prior and set(current) == set(REGIONS)
