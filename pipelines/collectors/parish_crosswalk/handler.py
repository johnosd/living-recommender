"""Coleta das duas planilhas de correspondência do INE (spec 004, FR-002 a FR-005)."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from pipelines.collectors._shared.datasets import collect_datasets
from pipelines.collectors.parish_crosswalk.validate import validate_crosswalk_table

SOURCE_ID = "ine_parish_crosswalk"


def collect_parish_crosswalk(
    catalog: dict[str, Any],
    *,
    storage: Any,
    downloader: Callable[[str, Path], Any],
    run_id: str,
    collected_at_utc: str,
    work_dir: Path,
    validator: Callable[[dict[str, Any], Path], None] = validate_crosswalk_table,
) -> dict[str, Any]:
    """Coleta cada tabela com estado próprio; a falha de uma não bloqueia a outra nem vira estado vigente."""

    def fetcher(dataset: dict[str, Any], destination: Path) -> dict[str, Any]:
        downloader(dataset["origin"], destination)
        return dict(getattr(downloader, "last_headers", None) or {})

    return collect_datasets(
        catalog, SOURCE_ID, storage=storage, fetcher=fetcher, validator=validator, run_id=run_id,
        collected_at_utc=collected_at_utc, work_dir=work_dir,
    )
