"""Carga manual de um dataset do Pordata que o site só oferece por botão (a planilha de poder de compra)."""

import shutil
from pathlib import Path
from typing import Any

from pipelines.collectors._shared.catalog import CatalogError, get_dataset_source
from pipelines.collectors._shared.datasets import (
    DatasetCollectionError,
    collect_datasets,
)
from pipelines.collectors.pordata.xlsx import validate_pordata_xlsx

SOURCE_ID = "pordata"
DEFAULT_DATASET = "poder_compra_per_capita_xlsx"


def load_pordata_manual(
    catalog: dict[str, Any],
    *,
    storage: Any,
    file: Path,
    run_id: str,
    collected_at_utc: str,
    work_dir: Path,
    dataset_id: str = DEFAULT_DATASET,
) -> dict[str, Any]:
    """Guarda a planilha entregue pelo operador como bruto rastreável, com estado e manifest próprios.

    O arquivo de origem só é lido (copiado para o temporário); nunca é alterado nem movido.
    """
    try:
        datasets = {d["id"]: d for d in get_dataset_source(catalog, SOURCE_ID)["datasets"]}
    except CatalogError as exc:
        raise DatasetCollectionError(f"catálogo: {exc}") from exc
    dataset = datasets.get(dataset_id)
    if dataset is None:
        raise DatasetCollectionError(f"dataset não cadastrado: {dataset_id}")
    if dataset["collection_method"] != "manual_upload":
        raise DatasetCollectionError(f"{dataset_id} é coletado por {dataset['collection_method']}, não por carga manual")

    def fetcher(_dataset: dict[str, Any], destination: Path) -> None:
        shutil.copyfile(file, destination)

    return collect_datasets(
        catalog, SOURCE_ID, storage=storage, fetcher=fetcher, validator=validate_pordata_xlsx, run_id=run_id,
        collected_at_utc=collected_at_utc, work_dir=work_dir, dataset_ids=[dataset_id],
    )
