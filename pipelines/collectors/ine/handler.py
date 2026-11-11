"""Coleta dos indicadores do INE pela API JSON."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from pipelines.collectors._shared.datasets import collect_datasets
from pipelines.collectors.ine.fetch import make_ine_fetcher
from pipelines.collectors.ine.fingerprint import fingerprint_ine_response
from pipelines.collectors.ine.validate import validate_ine_response

SOURCE_ID = "ine"


def collect_ine(
    catalog: dict[str, Any],
    *,
    storage: Any,
    downloader: Callable[[str, Path], Any],
    run_id: str,
    collected_at_utc: str,
    work_dir: Path,
    validator: Callable[[dict[str, Any], Path], None] = validate_ine_response,
) -> dict[str, Any]:
    """Coleta os indicadores do INE; a mudança é detectada sem o horário de extração."""
    return collect_datasets(
        catalog, SOURCE_ID, storage=storage, fetcher=make_ine_fetcher(downloader), validator=validator,
        run_id=run_id, collected_at_utc=collected_at_utc, work_dir=work_dir,
        fingerprint=lambda _dataset, path: fingerprint_ine_response(path),
    )
