"""Public CAOP collection boundary. Implemented during sdd-execute."""

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pipelines.collectors._shared.catalog import REGIONS, CatalogError, get_source
from pipelines.collectors._shared.manifest import (
    encode_manifest,
    file_digest,
    latest_changed,
    make_manifest,
    same_checksums,
)


class CollectionError(Exception):
    """A CAOP collection attempt failed after recording its outcome."""


def collect_caop(
    catalog: dict[str, dict[str, Any]],
    *,
    storage: Any,
    downloader: Callable[[str, Path], None],
    validator: Callable[[str, Path], None],
    run_id: str,
    collected_at_utc: str,
    work_dir: Path,
) -> dict[str, Any]:
    """Collect the configured three-region CAOP release into a storage backend."""
    try:
        source = get_source(catalog, strict_metadata=False)
    except CatalogError as exc:
        raise CollectionError(f"catálogo: {exc}") from exc
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", run_id):
        raise CollectionError("run_id inválido")
    manifest_key = f"manifests/caop/{run_id}.json"
    raw_prefix = f"raw/source=caop/version={source['version']}/run_id={run_id}/"
    try:  # antes de qualquer rede: o destino precisa aceitar escrita e listagem
        if hasattr(storage, "preflight"):
            storage.preflight()
        existing = storage.list_keys()
    except Exception as exc:
        raise CollectionError(f"destino sem permissão ou inacessível: {exc}") from exc
    if manifest_key in existing or any(key.startswith(raw_prefix) for key in existing):
        raise CollectionError(f"run_id já utilizado: {run_id}")

    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    committed: list[str] = []
    stage = "download"
    try:
        entries = []
        for region in REGIONS:
            destination = work_dir / f"{region}.gpkg.zip"
            downloaded.append(destination)
            downloader(source["urls"][region], destination)
            stage = f"validação {region}"
            validator(region, destination)
            key = f"{raw_prefix}{region}.gpkg.zip"
            entries.append(file_digest(destination, key=key, region=region))
            stage = "download"
        stage = "manifest anterior"
        previous = latest_changed(storage)
        if same_checksums(entries, previous):
            manifest = make_manifest(
                source,
                run_id=run_id,
                collected_at_utc=collected_at_utc,
                status="unchanged",
                files=previous["files"],
                previous_changed_run_id=previous["run_id"],
            )
        else:
            stage = "gravação raw"
            for entry, path in zip(entries, downloaded, strict=True):
                storage.put_file(entry["key"], path)
                committed.append(entry["key"])
            manifest = make_manifest(
                source,
                run_id=run_id,
                collected_at_utc=collected_at_utc,
                status="changed",
                files=entries,
            )
        stage = "manifest final"
        storage.put(manifest_key, encode_manifest(manifest))
        return {
            "status": manifest["status"],
            "run_id": run_id,
            "version": source["version"],
            "files": manifest["files"],
            "manifest_key": manifest_key,
        }
    except Exception as exc:
        for key in committed:
            storage.delete(key)
        error = f"{stage}: {exc}"
        failed = make_manifest(
            source,
            run_id=run_id,
            collected_at_utc=collected_at_utc,
            status="failed",
            error=error,
        )
        try:
            storage.put(manifest_key, encode_manifest(failed))
        except Exception as manifest_exc:  # noqa: BLE001 - backends may raise SDK errors
            raise CollectionError(f"{error}; não foi possível registrar falha: {manifest_exc}") from exc
        raise CollectionError(error) from exc
    finally:
        for path in downloaded:
            path.unlink(missing_ok=True)
        try:
            work_dir.rmdir()
        except OSError:
            pass
