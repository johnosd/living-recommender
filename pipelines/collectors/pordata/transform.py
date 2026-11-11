"""CSV do Pordata → observações municipais em formato longo (ainda sem o `dico`)."""

from pathlib import Path
from typing import Any

import pandas as pd

from pipelines.collectors._shared.observations import RAW_COLUMNS
from pipelines.collectors.pordata.validate import (
    MUNICIPALITY_SCOPE,
    SCOPE_LABEL,
    PordataSchemaError,
    label_index,
)
from pipelines.collectors.pordata.xlsx import EMPTY_SYMBOL, parse_pordata_xlsx


def read_pordata_csv(dataset: dict[str, Any], path: Path) -> tuple[pd.DataFrame, int]:
    """Só as linhas de município; devolve também quantas linhas de agregação foram excluídas.

    As colunas são lidas pelo rótulo (o prefixo numérico varia por dataset). Valor vazio vira
    nulo e o símbolo da fonte é preservado; nada é convertido em zero.
    """
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    index = label_index(list(frame.columns))
    scope = index.get(SCOPE_LABEL)
    if scope is None:
        raise PordataSchemaError(f"{dataset['id']}: coluna ausente: {SCOPE_LABEL}")
    municipal = frame.iloc[:, scope] == MUNICIPALITY_SCOPE
    excluded = int((~municipal).sum())
    selected = frame[municipal]

    def column(label: str, *, strip: bool = True) -> pd.Series:
        position = index.get(label)
        if position is None:
            return pd.Series("", index=selected.index, dtype=str)
        values = selected.iloc[:, position]
        return values.str.strip() if strip else values

    raw_value = column("Valor")
    symbol = column("Símbolo")
    result = pd.DataFrame({
        "source_name": column(dataset["name_column"], strip=False),
        "period": pd.to_numeric(column("Ano"), errors="raise").astype("int64"),
        "filter_1": column("Filtro 1"),
        "filter_2": column("Filtro 2"),
        "filter_3": column("Filtro 3"),
        "value": pd.to_numeric(raw_value.where(raw_value != ""), errors="raise"),
        "symbol": symbol.where(symbol != "", None),
        "unit": column("Escala"),
    })
    return result[RAW_COLUMNS].reset_index(drop=True), excluded


def read_pordata_xlsx(dataset: dict[str, Any], path: Path) -> tuple[pd.DataFrame, int]:
    """Planilha manual → formato longo: uma observação por município e ano; agregações NUTS contadas.

    Célula vazia vira valor nulo com o símbolo `vazio`; texto no lugar do número (por exemplo `x`)
    vira nulo com esse texto como símbolo. Nada é convertido em zero.
    """
    years, rows = parse_pordata_xlsx(dataset, path)
    records, excluded = [], 0
    for scope, name, values in rows:
        if scope != MUNICIPALITY_SCOPE:
            excluded += scope.upper().startswith("NUTS")  # linhas de legenda do rodapé não contam
            continue
        for year, cell in zip(years, values, strict=False):
            value, symbol = None, None
            if cell is None or str(cell).strip() == "":
                symbol = EMPTY_SYMBOL
            else:
                try:
                    value = float(str(cell).replace(",", "."))
                except ValueError:
                    symbol = str(cell).strip()
            records.append({"source_name": name, "period": year, "filter_1": "", "filter_2": "",
                            "filter_3": "", "value": value, "symbol": symbol, "unit": dataset["unit"]})
    frame = pd.DataFrame(records, columns=RAW_COLUMNS)
    frame["value"] = frame["value"].astype("float64")
    frame["period"] = frame["period"].astype("int64")
    return frame, int(excluded)
