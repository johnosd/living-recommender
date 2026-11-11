"""Coleta dos datasets do Pordata disponíveis por HTTP."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from pipelines.collectors._shared.catalog import CatalogError, get_dataset_source
from pipelines.collectors._shared.datasets import (
    DatasetCollectionError,
    collect_datasets,
)
from pipelines.collectors.pordata.validate import validate_pordata_csv

SOURCE_ID = "pordata"


def http_dataset_ids(catalog: dict[str, Any]) -> list[str]:
    """Os datasets baixáveis por HTTP; a planilha manual entra por `load_pordata_manual`."""
    try:
        source = get_dataset_source(catalog, SOURCE_ID)
    except CatalogError as exc:
        raise DatasetCollectionError(f"catálogo: {exc}") from exc
    return [d["id"] for d in source["datasets"] if d["collection_method"] == "http_download"]


def collect_pordata(
    catalog: dict[str, Any],
    *,
    storage: Any,
    downloader: Callable[[str, Path], Any],
    run_id: str,
    collected_at_utc: str,
    work_dir: Path,
    validator: Callable[[dict[str, Any], Path], None] = validate_pordata_csv,
) -> dict[str, Any]:
    """Coleta os CSV do Pordata, cada um com estado próprio; falha de um não bloqueia os outros."""

    def fetcher(dataset: dict[str, Any], destination: Path) -> dict[str, Any]:
        downloader(dataset["origin"], destination)
        return dict(getattr(downloader, "last_headers", None) or {})

    return collect_datasets(
        catalog, SOURCE_ID, storage=storage, fetcher=fetcher, validator=validator, run_id=run_id,
        collected_at_utc=collected_at_utc, work_dir=work_dir, dataset_ids=http_dataset_ids(catalog),
    )
