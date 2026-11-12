"""Leitura das planilhas do INE para tabelas normalizadas (spec 004, FR-006)."""

from pathlib import Path
from typing import Any

import pandas as pd

from pipelines.collectors.parish_crosswalk.layout import (
    CrosswalkSchemaError,
    is_partial,
    load_rows,
)

TABLE_A_ROLE, TABLE_B_ROLE = "pre2013_to_2013", "pre2013_to_2025"
TABLE_A_COLUMNS = ["pre_code", "pre_name", "name_2013", "code_2013", "partial_origin"]
TABLE_B_COLUMNS = ["pre_code", "pre_name", "municipality_name", "code_2025", "name_2025"]


def read_crosswalk_table(dataset: dict[str, Any], path: Path) -> tuple[pd.DataFrame, dict[str, int]]:
    """Devolve ``(tabela, estatísticas)``.

    Tabela A (`role=pre2013_to_2013`): ``pre_code, pre_name, name_2013, code_2013, partial_origin``.
    Tabela B (`role=pre2013_to_2025`): ``pre_code, pre_name, municipality_name, code_2025, name_2025``.
    Estatísticas: ``rows_read, ignored_rows, numeric_codes_normalized, partial_rows``.
    """
    role = dataset.get("role")
    rows, stats = load_rows(dataset, path)
    if role == TABLE_A_ROLE:
        frame = pd.DataFrame(
            [(r["pre_code"], r["pre_name"], r.get("name", ""), r["code"], is_partial(r["pre_name"])) for r in rows],
            columns=TABLE_A_COLUMNS,
        )
        frame["partial_origin"] = frame["partial_origin"].astype(bool)
    elif role == TABLE_B_ROLE:
        frame = pd.DataFrame(
            [(r["pre_code"], r["pre_name"], r.get("municipality_name", ""), r["code"], r.get("name", ""))
             for r in rows],
            columns=TABLE_B_COLUMNS,
        )
    else:
        raise CrosswalkSchemaError(f"{dataset['id']}: role desconhecido: {role!r}")
    return frame, stats
