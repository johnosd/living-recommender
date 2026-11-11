"""Resposta JSON do Open-Meteo → observações diárias em formato longo, ainda sem o ``dico`` (spec 003).

STUB do sdd-plan: implementado na Fase 5 (T024).
"""

from pathlib import Path

import pandas as pd

COLUMNS = ["variable", "date", "value", "unit"]


def read_climate_response(path: Path) -> pd.DataFrame:
    """Uma linha por variável e dia. ``date`` é ``datetime.date`` (dia local do município, sem fuso);
    ``value`` é ``float64`` com ``NaN`` onde a fonte tem ``null``; ``unit`` vem de ``daily_units``.
    """
    raise NotImplementedError("not implemented: read_climate_response (T024)")
