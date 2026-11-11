"""Esquema do Parquet longo de observações municipais (entrada do dbt `stg_observation`)."""

from typing import Any

import pandas as pd

# O que cada transformação (CSV, JSON, XLSX) produz, ainda sem o município resolvido.
RAW_COLUMNS = ["source_name", "period", "filter_1", "filter_2", "filter_3", "value", "symbol", "unit"]
# Colunas finais, na ordem em que o dbt as lê.
COLUMNS = [
    "source_id", "dataset_id", "dico", "source_name", "period", "filter_1", "filter_2", "filter_3",
    "value", "symbol", "unit", "source_run_id", "license_id", "attribution", "collected_at_utc",
    "processed_at_utc",
]
STATS_COLUMNS = ["source_id", "dataset_id", "aggregate_rows_excluded", "rows_read"]


def finalize(
    frame: pd.DataFrame, *, source: dict[str, Any], dataset: dict[str, Any], state: dict[str, Any],
    dico: pd.Series, processed_at_utc: str,
) -> pd.DataFrame:
    """Acrescenta o município resolvido e a proveniência (fonte, execução, licença, datas)."""
    result = frame.copy()
    result["source_id"] = source["id"]
    result["dataset_id"] = dataset["id"]
    result["dico"] = dico.to_numpy()
    result["source_run_id"] = state["run_id"]
    result["license_id"] = source["license_id"]
    result["attribution"] = source.get("attribution")
    result["collected_at_utc"] = state["collected_at_utc"]
    result["processed_at_utc"] = processed_at_utc
    return result[COLUMNS]
