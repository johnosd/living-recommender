"""Resposta JSON do INE → observações municipais em formato longo (ainda sem o `dico`)."""

from pathlib import Path
from typing import Any

import pandas as pd

from pipelines.collectors._shared.observations import RAW_COLUMNS
from pipelines.collectors.ine.validate import MUNICIPAL_CODE_LENGTH, load_ine_document


def read_ine_response(dataset: dict[str, Any], path: Path) -> tuple[pd.DataFrame, int]:
    """Uma linha por período e município; `source_name` é o `geocod` (os 4 últimos caracteres são o `dico`).

    Ausência (`sinal_conv`, sem `valor`) vira valor nulo com o símbolo preservado. A categoria de crime
    (`dim_3_t`) vai para `filter_1`. Códigos que não são municipais são excluídos e contados.
    """
    document = load_ine_document(path)
    rows, excluded = [], 0
    for period, items in document["Dados"].items():
        for item in items:
            geocod = str(item.get("geocod", ""))
            if len(geocod) != MUNICIPAL_CODE_LENGTH:
                excluded += 1
                continue
            raw = item.get("valor")
            rows.append({
                "source_name": geocod,
                "period": int(period),
                "filter_1": item.get("dim_3_t") or "",
                "filter_2": "",
                "filter_3": "",
                "value": float(raw) if raw not in (None, "") else None,
                "symbol": item.get("sinal_conv"),
                "unit": dataset["unit"],
            })
    frame = pd.DataFrame(rows, columns=RAW_COLUMNS)
    frame["value"] = frame["value"].astype("float64")
    return frame, excluded
