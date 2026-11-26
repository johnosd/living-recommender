"""Códigos fechados e colunas da camada Gold (spec 011, `data-model.md`)."""
import re

import pandas as pd

STATUSES = ("disponivel", "fonte_pendente")
VALUE_STATUSES = ("observado", "zero_convencao_fonte", "ausente")
ORIGINS = ("proprio", "herdado", "ausente")
SAMPLE_STATUSES = ("suficiente", "amostra_insuficiente", "sem_anuncios")
RENT_COVERAGES = ("propria", "insuficiente", "regional_only", "sem_anuncios")
TYPOLOGIES = ("ALL", "T0", "T1", "T2", "T3", "T4+")
LEVELS = ("municipio", "freguesia")
DIRECTIONS = ("maior_melhor", "menor_melhor", "faixa_alvo")
MODES = ("peso", "faixa", "opcao")
KINDS = ("observation", "climate", "mobility", "rent", "census")

# `logic/indicadores.md` §3; `simbolo_fonte:<s>` leva o símbolo da fonte depois dos dois pontos.
MISSING_REASONS = ("sem_publicacao", "sem_denominador", "sem_par_elegivel", "sem_rota", "par_falha",
                   "par_pendente", "amostra_insuficiente", "sem_anuncios", "regional_only", "sem_dados_clima")
SYMBOL_REASON_PREFIX = "simbolo_fonte:"

MIN_SAMPLE = 10  # constitution III: nenhuma mediana de aluguel abaixo de 10 anúncios

INDICATOR_COLUMNS = ("dico", "criterion_id", "category", "variant", "value", "unit", "period",
                     "dataset_latest_period", "is_older_period", "value_status", "missing_reason", "source_symbol",
                     "source_id", "dataset_id", "license_id", "attribution", "usage_restriction", "is_stale")

_SPACES = re.compile(r"\s+")


def normalize_label(text) -> str:
    """Rótulo de filtro comparável: NBSP vira espaço, espaços repetidos colapsam e as pontas somem (R-008)."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ""
    return _SPACES.sub(" ", str(text).replace("\xa0", " ")).strip()


def indicator_row(dico: str, criterion: dict, **values) -> dict:
    """Linha de indicador com os campos do catálogo preenchidos e o resto nulo; `values` sobrescreve."""
    row = {column: None for column in INDICATOR_COLUMNS}
    row.update({"dico": dico, "criterion_id": criterion["id"], "category": criterion["category"], "variant": "",
                "unit": criterion.get("unit"), "is_older_period": False, "is_stale": False})
    row.update(values)
    if row["value"] is None or (isinstance(row["value"], float) and pd.isna(row["value"])):
        row["value"] = None
        row["value_status"] = "ausente"
    elif row.get("value_status") is None:
        row["value_status"] = "observado"
    return row


def indicator_frame(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=list(INDICATOR_COLUMNS))
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce").astype("float64")
    frame["is_older_period"] = frame["is_older_period"].fillna(False).astype(bool)
    frame["is_stale"] = frame["is_stale"].fillna(False).astype(bool)
    return frame


def available(criteria: dict, kind: str, level: str = "municipio") -> list[dict]:
    """Critérios `disponivel` do `kind` pedido, que declaram o nível."""
    return [item for item in criteria["criteria"]
            if item.get("status") == "disponivel" and level in (item.get("levels") or [])
            and (item.get("compute") or {}).get("kind") == kind]
