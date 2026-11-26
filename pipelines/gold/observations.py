"""Indicadores municipais a partir das observações do Pordata e do INE (`stg_observation`).

Regras (período mais recente por município, `-` como zero em contagens, denominador do mesmo período):
`.sdd/specs/011-marts-indicadores-catalogo/logic/indicadores.md` §1.
"""
from dataclasses import dataclass

import pandas as pd

from pipelines.gold.common import (
    SYMBOL_REASON_PREFIX,
    available,
    indicator_frame,
    indicator_row,
    normalize_label,
)

POPULATION_DATASET = "populacao_residente_sexo_idade"
FILTER_KEYS = ("filter_1", "filter_2", "filter_3")
SEPARATOR = "\x1f"
PROVENANCE = ("source_id", "dataset_id", "license_id", "attribution")


@dataclass(frozen=True)
class Cell:
    """Numerador (ou denominador) de um município num período: a soma das partes, ou o motivo de não haver."""

    value: float | None
    reason: str | None
    used_dash: bool
    symbols: tuple[str, ...]
    provenance: dict


def _key(part: dict) -> str:
    return SEPARATOR.join(normalize_label(part.get(key, "")) for key in FILTER_KEYS)


def _prepare(observations: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Observações por dataset, com a chave de filtro normalizada (NBSP e espaços, R-008)."""
    frame = observations.copy()
    for column in FILTER_KEYS:
        if column not in frame.columns:
            frame[column] = ""
        raw = frame[column].astype(object).where(frame[column].notna(), "")
        mapping = {value: normalize_label(value) for value in pd.unique(raw)}
        frame[column] = raw.map(mapping)
    frame["filter_key"] = frame["filter_1"] + SEPARATOR + frame["filter_2"] + SEPARATOR + frame["filter_3"]
    if "symbol" not in frame.columns:
        frame["symbol"] = None
    return {dataset: group for dataset, group in frame.groupby("dataset_id", sort=False)}


def _symbol(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)) or str(value).strip() == "":
        return None
    return str(value).strip()


def _cells(rows: pd.DataFrame | None, parts: list[str], dash_is_zero: bool) -> dict[tuple, Cell]:
    """(dico, período) -> soma das partes `parts`; nula se faltar alguma parte ou alguma for nula."""
    if rows is None or rows.empty:
        return {}
    selected = rows[rows["filter_key"].isin(parts)]
    order = {part: index for index, part in enumerate(parts)}
    grouped: dict[tuple, list] = {}
    for row in selected.itertuples(index=False):
        grouped.setdefault((row.dico, row.period), []).append(row)
    cells = {}
    for key, lines in grouped.items():
        lines.sort(key=lambda line: order[line.filter_key])
        total, reason, used_dash, present = 0.0, None, False, set()
        for line in lines:
            present.add(line.filter_key)
            symbol = _symbol(line.symbol)
            if not pd.isna(line.value):
                total += float(line.value)
            elif symbol == "-" and dash_is_zero:
                used_dash = True  # R-001: contagem com "-" é zero pela convenção da fonte
            elif reason is None:
                reason = SYMBOL_REASON_PREFIX + symbol if symbol else "sem_publicacao"
        if reason is None and len(present) < len(parts):
            reason = "sem_publicacao"
        symbols = tuple(sorted({s for s in (_symbol(line.symbol) for line in lines) if s}))
        provenance = {column: getattr(lines[0], column, None) for column in PROVENANCE}
        cells[key] = Cell(None if reason else total, reason, used_dash, symbols, provenance)
    return cells


def _population_parts(age_groups) -> list[str]:
    groups = age_groups or ["Total"]
    return [_key({"filter_1": "Total", "filter_2": group}) for group in groups]


def _dataset_provenance(rows: pd.DataFrame | None, compute: dict) -> dict:
    provenance = {"source_id": compute.get("source_id"), "dataset_id": compute.get("dataset_id"),
                  "license_id": None, "attribution": None}
    if rows is not None and not rows.empty:
        first = rows.iloc[0]
        provenance.update({column: first.get(column) for column in PROVENANCE if column in rows.columns})
    return provenance


def _criterion_rows(criterion: dict, datasets: dict[str, pd.DataFrame], dicos: list[str],
                    population_cache: dict) -> list[dict]:
    compute = criterion["compute"]
    rows = datasets.get(compute.get("dataset_id"))
    dash_is_zero = bool(compute.get("dash_is_zero"))
    numerators = _cells(rows, [_key(part) for part in compute.get("filters") or [{}]], dash_is_zero)
    denominators = None
    if compute.get("per_population"):
        groups = compute["per_population"].get("age_groups")
        cache_key = tuple(groups or ())
        if cache_key not in population_cache:
            population_cache[cache_key] = _cells(datasets.get(POPULATION_DATASET), _population_parts(groups), True)
        denominators, scale = population_cache[cache_key], float(compute["per_population"]["scale"])
    elif compute.get("share"):
        denominators = _cells(rows, [_key(compute["share"]["filters"])], dash_is_zero)
        scale = float(compute["share"]["scale"])

    by_dico: dict[str, dict] = {}
    for (dico, period), cell in numerators.items():
        by_dico.setdefault(dico, {})[period] = cell
    valid_periods = [period for cells in by_dico.values() for period, cell in cells.items() if cell.value is not None]
    latest = max(valid_periods) if valid_periods else None
    latest_text = None if latest is None else str(latest)
    fallback = _dataset_provenance(rows, compute)

    output = []
    for dico in dicos:
        cells = by_dico.get(dico, {})
        valid = [period for period, cell in cells.items() if cell.value is not None]
        common = {"dataset_latest_period": latest_text, "usage_restriction": None}
        if not valid:
            reason = cells[max(cells)].reason if cells else "sem_publicacao"
            output.append(indicator_row(dico, criterion, value=None, missing_reason=reason, **fallback, **common))
            continue
        period = max(valid)
        cell = cells[period]
        base = {**common, **fallback, **{k: v for k, v in cell.provenance.items() if v is not None},
                "period": str(period), "is_older_period": bool(period < latest),
                "source_symbol": "|".join(cell.symbols) or None}
        value = cell.value
        if denominators is not None:
            denominator = denominators.get((dico, period))
            if denominator is None or denominator.value is None or denominator.value == 0:
                output.append(indicator_row(dico, criterion, value=None, missing_reason="sem_denominador", **base))
                continue
            value = value * scale / denominator.value
        if compute.get("presence"):
            value = 1.0 if cell.value > 0 else 0.0
        status = "zero_convencao_fonte" if cell.used_dash and value == 0 else "observado"
        output.append(indicator_row(dico, criterion, value=float(value), value_status=status, **base))
    return output


def municipal_indicators(observations: pd.DataFrame, municipalities: pd.DataFrame, criteria: dict) -> pd.DataFrame:
    """Uma linha por município x critério disponível com `compute.kind == "observation"`, valor ou ausência."""
    datasets = _prepare(observations)
    dicos = list(municipalities["dico"])
    population_cache: dict = {}
    rows = []
    for criterion in available(criteria, "observation"):
        rows.extend(_criterion_rows(criterion, datasets, dicos, population_cache))
    return indicator_frame(rows)
