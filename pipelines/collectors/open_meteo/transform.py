"""JSON diário para observações longas; datas locais e ausências preservadas."""
import json
from datetime import date
from pathlib import Path

import pandas as pd

COLUMNS = ["variable", "date", "value", "unit"]


def read_climate_response(path: Path, *, variables=None) -> pd.DataFrame:
    doc = json.loads(path.read_text(encoding="utf-8"))
    days = [date.fromisoformat(day) for day in doc["daily"]["time"]]
    rows = [(variable, day, value, doc["daily_units"][variable])
            for variable, values in doc["daily"].items()
            if variable != "time" and (variables is None or variable in variables)
            for day, value in zip(days, values, strict=True)]
    frame = pd.DataFrame(rows, columns=COLUMNS)
    frame["value"] = frame["value"].astype("float64")
    return frame
