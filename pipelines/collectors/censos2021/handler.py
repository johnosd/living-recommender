"""Fronteira pública da coleta."""

import hashlib
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

from pipelines.collectors._shared.datasets import collect_datasets
from pipelines.collectors.censos2021.validate import (
    load_document,
    query_signature,
    validate_censos_catalog,
    validate_censos_response,
)
from pipelines.collectors.ine.fetch import build_url
from pipelines.collectors.ine.fingerprint import fingerprint_ine_response


def collect_censos(
    catalog: dict[str, Any],
    *,
    storage: Any,
    downloader: Callable,
    run_id: str,
    collected_at_utc: str,
    work_dir: Path,
) -> dict[str, Any]:
    """Manifest v2 da fonte censos; dados e metadados imutáveis por dataset."""
    source = deepcopy(validate_censos_catalog(catalog))
    for dataset in source["datasets"]:
        dataset.setdefault("license_id", source["license_id"])
        dataset.setdefault(
            "attribution", source.get("attribution", "INE — Censos 2021")
        )

    def fetch(dataset, path):
        url = dataset["origin"] if dataset["role"] == "metadata" else build_url(dataset)
        downloader(url, path)
        doc = load_document(path)
        return {
            "reference_period": "2021",
            "source_release_date": doc.get("DataUltimaAtualizacao")
            or doc.get("DataUltimoAtualizacao"),
            "entry_extra": {
                "origin": url,
                "dataset_snapshot": deepcopy(dataset),
                "query_signature": query_signature(dataset),
                "geography_version": dataset["geography_version"],
            },
        }

    def fingerprint(dataset, path):
        return hashlib.sha256(
            (query_signature(dataset) + fingerprint_ine_response(path)).encode()
        ).hexdigest()

    return collect_datasets(
        {"sources": {"censos": source}},
        "censos",
        storage=storage,
        fetcher=fetch,
        validator=validate_censos_response,
        run_id=run_id,
        collected_at_utc=collected_at_utc,
        work_dir=work_dir,
        fingerprint=fingerprint,
    )
