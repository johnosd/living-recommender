"""Coleta de uma fonte com vários datasets independentes (Pordata, INE).

Cada dataset tem estado vigente próprio; a falha de um não impede os demais e não vira
estado. Ver `sdd/specs/002-ingestao-pordata-ine/logic/ingestao-datasets.md` §1.
"""

import contextlib
import hashlib
import re
import shutil
from collections.abc import Callable, Collection
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pipelines.collectors._shared.catalog import CatalogError, get_dataset_source
from pipelines.collectors._shared.dataset_manifest import (
    encode_dataset_manifest,
    latest_dataset_states,
    make_dataset_manifest,
)

RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
EXTENSIONS = {"csv": ".csv", "json": ".json", "xlsx": ".xlsx"}


class DatasetCollectionError(Exception):
    """A coleta não pôde começar (catálogo, run_id ou destino); nada foi baixado."""


class StopCollection(Exception):
    """Um fetcher pede o fim limpo da coleta: o item atual e os seguintes ficam `pending` (spec 003)."""


class QuotaExhausted(StopCollection):
    """A fonte recusou novas chamadas por cota; a coleta para e a próxima execução continua (spec 003)."""


def _suffix(dataset: dict[str, Any]) -> str:
    if dataset.get("format") in EXTENSIONS:
        return EXTENSIONS[dataset["format"]]
    if dataset["collection_method"] == "api_json":
        return ".json"
    suffix = Path(urlparse(dataset.get("origin") or "").path).suffix.lower()
    return suffix if suffix in EXTENSIONS.values() else ".bin"


def _sha256_and_size(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _entry(dataset: dict[str, Any], status: str, **fields: Any) -> dict[str, Any]:
    entry = {
        "dataset_id": dataset["id"],
        "origin": dataset.get("origin") or dataset.get("indicator"),
        "collection_method": dataset.get("collection_method"),
        "status": status,
        "key": None,
        "sha256": None,
        "bytes": None,
        "fingerprint": None,
        "reference_period": None,
        "source_release_date": None,
        "http": None,
        "error": None,
        "previous_changed_run_id": None,
    }
    entry.update(fields)
    return entry


def _collect_one(
    dataset: dict[str, Any], *, source_id: str, state: dict[str, Any] | None, storage: Any,
    fetcher: Callable[[dict[str, Any], Path], Any], validator: Callable[[dict[str, Any], Path], None],
    fingerprint: Callable[[dict[str, Any], Path], str] | None, run_id: str, work_dir: Path,
) -> dict[str, Any]:
    suffix = _suffix(dataset)
    path = work_dir / f"{dataset['id']}{suffix}"
    stage, written = "download", None
    try:
        meta = fetcher(dataset, path)
        meta = meta if isinstance(meta, dict) else {}
        stage = "validação"
        validator(dataset, path)
        stage = "impressão digital"
        sha256, size = _sha256_and_size(path)
        fp = fingerprint(dataset, path) if fingerprint else sha256
        common = {
            "reference_period": meta.get("reference_period"),
            "source_release_date": meta.get("source_release_date"),
            "http": {k: meta[k] for k in ("etag", "last_modified") if meta.get(k)} or None,
        }
        if state is not None and state["fingerprint"] == fp:
            return _entry(
                dataset, "unchanged", key=state["key"], sha256=state["sha256"], bytes=state["bytes"],
                fingerprint=fp, previous_changed_run_id=state["run_id"], **common,
            )
        stage = "gravação raw"
        key = f"raw/source={source_id}/dataset={dataset['id']}/run_id={run_id}/{dataset['id']}{suffix}"
        storage.put_file(key, path)
        written = key
        return _entry(dataset, "changed", key=key, sha256=sha256, bytes=size, fingerprint=fp, **common)
    except Exception as exc:  # noqa: BLE001 - fetchers/validators/backends lançam erros variados
        if written:  # limpeza best effort; o erro original é o que vale
            with contextlib.suppress(Exception):
                storage.delete(written)
        return _entry(dataset, "failed", error=f"{stage}: {exc}")
    finally:
        path.unlink(missing_ok=True)


def collect_datasets(
    catalog: dict[str, Any],
    source_id: str,
    *,
    storage: Any,
    fetcher: Callable[[dict[str, Any], Path], Any],
    validator: Callable[[dict[str, Any], Path], None],
    run_id: str,
    collected_at_utc: str,
    work_dir: Path,
    fingerprint: Callable[[dict[str, Any], Path], str] | None = None,
    dataset_ids: Collection[str] | None = None,
) -> dict[str, Any]:
    """Coleta cada dataset da fonte de forma independente e grava o manifest v2.

    ``fetcher(dataset, destino)`` baixa para o temporário e pode devolver um ``dict`` com
    ``etag``, ``last_modified``, ``reference_period`` e ``source_release_date``.
    Retorna ``{"status", "run_id", "manifest_key", "datasets": [...]}`` e NÃO levanta
    exceção por falha de um dataset (``partial``/``failed`` são resultados).
    """
    try:
        source = get_dataset_source(catalog, source_id)
    except CatalogError as exc:
        raise DatasetCollectionError(f"catálogo: {exc}") from exc
    datasets = source["datasets"]
    if dataset_ids is not None:
        unknown = sorted(set(dataset_ids) - {dataset["id"] for dataset in datasets})
        if unknown:
            raise DatasetCollectionError(f"dataset não cadastrado: {', '.join(unknown)}")
        datasets = [dataset for dataset in datasets if dataset["id"] in set(dataset_ids)]
    if not RUN_ID.fullmatch(run_id):
        raise DatasetCollectionError("run_id inválido")
    manifest_key = f"manifests/{source_id}/{run_id}.json"
    try:  # antes de qualquer rede: o destino precisa aceitar escrita e listagem
        if hasattr(storage, "preflight"):
            storage.preflight()
        existing = storage.list_keys()
        states = latest_dataset_states(storage, source_id)
    except Exception as exc:
        raise DatasetCollectionError(f"destino sem permissão ou inacessível: {exc}") from exc
    marker = f"/run_id={run_id}/"
    if manifest_key in existing or any(
        key.startswith(f"raw/source={source_id}/") and marker in key for key in existing
    ):
        raise DatasetCollectionError(f"run_id já utilizado: {run_id}")

    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    try:
        for dataset in datasets:
            entries.append(_collect_one(
                dataset, source_id=source_id, state=states.get(dataset["id"]), storage=storage,
                fetcher=fetcher, validator=validator, fingerprint=fingerprint, run_id=run_id,
                work_dir=work_dir,
            ))
        manifest = make_dataset_manifest(
            source, source_id=source_id, run_id=run_id, collected_at_utc=collected_at_utc,
            datasets=entries,
        )
        try:
            storage.put(manifest_key, encode_dataset_manifest(manifest))
        except Exception as exc:
            for entry in entries:  # sem manifest o raw deste run ficaria órfão
                if entry["status"] == "changed":
                    with contextlib.suppress(Exception):
                        storage.delete(entry["key"])
            raise DatasetCollectionError(f"manifest não gravado: {exc}") from exc
        return {
            "status": manifest["status"], "run_id": run_id, "manifest_key": manifest_key,
            "datasets": entries,
        }
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
