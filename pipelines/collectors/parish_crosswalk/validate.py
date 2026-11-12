"""Validação das planilhas do INE antes de serem aceitas como bruto (spec 004, FR-005)."""

from pathlib import Path
from typing import Any

from pipelines.collectors.parish_crosswalk.layout import CrosswalkSchemaError, load_rows

__all__ = ["CrosswalkSchemaError", "validate_crosswalk_table"]


def validate_crosswalk_table(dataset: dict[str, Any], path: Path) -> None:
    """Reprova arquivo que não é planilha, aba ou coluna ausente, código inválido e planilha sem linhas de dado."""
    rows, _ = load_rows(dataset, path)
    if not rows:
        raise CrosswalkSchemaError(f"{dataset['id']}: nenhuma linha de dado")
