"""Manifest v2: uma execução com vários datasets independentes, cada um com seu estado.

Convive com o manifest v1 da CAOP (`manifest.py`, `files[]`), que não é alterado.
"""

import json
from datetime import datetime, timedelta

from pipelines.collectors._shared.manifest import encode_manifest

SCHEMA_VERSION = 2
RUN_STATUSES = {"changed", "unchanged", "partial", "failed"}
DATASET_STATUSES = {"changed", "unchanged", "failed"}


class DatasetManifestError(ValueError):
    """Manifest v2 inválido ou incompleto."""


def run_status(entries: list[dict]) -> str:
    """changed | unchanged | partial | failed, a partir do status de cada dataset."""
    if not entries:
        raise DatasetManifestError("execução sem datasets")
    statuses = [entry["status"] for entry in entries]
    failed = statuses.count("failed")
    if failed == len(statuses):
        return "failed"
    if failed:
        return "partial"
    return "changed" if "changed" in statuses else "unchanged"


def validate_entry(entry: dict) -> None:
    if not isinstance(entry, dict) or not entry.get("dataset_id"):
        raise DatasetManifestError("entrada de dataset sem dataset_id")
    status = entry.get("status")
    if status not in DATASET_STATUSES:
        raise DatasetManifestError(f"status de dataset desconhecido: {status}")
    if status == "failed":
        if not entry.get("error"):
            raise DatasetManifestError("falha exige mensagem de erro")
        return
    if not isinstance(entry.get("key"), str) or not entry["key"].startswith("raw/"):
        raise DatasetManifestError("chave raw inválida")
    if not isinstance(entry.get("sha256"), str) or len(entry["sha256"]) != 64:
        raise DatasetManifestError("checksum inválido")
    if not isinstance(entry.get("bytes"), int) or entry["bytes"] <= 0:
        raise DatasetManifestError("tamanho inválido")
    if not isinstance(entry.get("fingerprint"), str) or not entry["fingerprint"]:
        raise DatasetManifestError("impressão digital ausente")
    if status == "unchanged" and not entry.get("previous_changed_run_id"):
        raise DatasetManifestError("unchanged exige previous_changed_run_id")


def make_dataset_manifest(
    source: dict, *, source_id: str, run_id: str, collected_at_utc: str, datasets: list[dict]
) -> dict:
    if not run_id or "/" in run_id or "\\" in run_id or run_id in (".", ".."):
        raise DatasetManifestError("run_id inválido")
    try:
        parsed = datetime.fromisoformat(collected_at_utc)
    except ValueError as exc:
        raise DatasetManifestError("collected_at_utc inválido") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise DatasetManifestError("collected_at_utc deve estar em UTC")
    for entry in datasets:
        validate_entry(entry)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "source_id": source_id,
        "run_id": run_id,
        "collected_at_utc": collected_at_utc,
        "status": run_status(datasets),
        "license_id": source["license_id"],
        "collection_method": source["collection_method"],
        "datasets": datasets,
    }
    if source.get("attribution"):
        manifest["attribution"] = source["attribution"]
    return manifest


def encode_dataset_manifest(manifest: dict) -> bytes:
    return encode_manifest(manifest)


def latest_dataset_states(storage, source_id: str) -> dict[str, dict]:
    """Estado vigente por dataset: a entrada `changed` mais recente em qualquer manifest da fonte.

    Um manifest `partial` conta para os datasets que tiveram sucesso. `failed` e `unchanged`
    nunca são estado. Desempate por horário e depois por `run_id`.
    """
    prefix = f"manifests/{source_id}/"
    best: dict[str, tuple[tuple[datetime, str], dict]] = {}
    for key in sorted(storage.list_keys()):
        if not key.startswith(prefix) or not key.endswith(".json"):
            continue
        try:
            manifest = json.loads(storage.get(key))
        except (ValueError, TypeError) as exc:
            raise DatasetManifestError(f"JSON inválido: {key}") from exc
        if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("source_id") != source_id:
            continue
        order = (datetime.fromisoformat(manifest["collected_at_utc"]), manifest["run_id"])
        for entry in manifest.get("datasets", []):
            if entry.get("status") != "changed":
                continue
            validate_entry(entry)
            current = best.get(entry["dataset_id"])
            if current is None or order > current[0]:
                best[entry["dataset_id"]] = (order, {**entry, "run_id": manifest["run_id"],
                                                     "collected_at_utc": manifest["collected_at_utc"]})
    return {dataset_id: state for dataset_id, (_, state) in best.items()}
