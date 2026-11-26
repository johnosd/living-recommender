"""`criteria_catalog`: leitura e validação de `config/criteria.yml`, parâmetros de normalização e versão.

Formato do arquivo e das tabelas: `.sdd/specs/011-marts-indicadores-catalogo/contracts/criteria-catalog.md`.
Toda mensagem de erro cita o id do critério ou da categoria entre aspas simples.
"""
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from pipelines.gold.common import DIRECTIONS, KINDS, LEVELS, MODES, STATUSES, TYPOLOGIES

WEIGHT_TOLERANCE = 1e-9
CLIMATE_METRICS = ("temp_media_anual", "temp_max_anual", "temp_min_anual", "temp_max_verao", "temp_min_inverno", "precipitacao_anual", "sol_horas_dia",
                   "dias_calor_pct", "dias_frio_pct", "dias_chuva_pct", "dias_neve_pct", "dias_extremos_pct",
                   "tci_anual")
CENSUS_METRICS = ("residentes", "pct_25_39", "pct_65_mais", "densidade")
RENT_METRICS = ("median", "eur_m2_median")
MOBILITY_MODES = ("straight_line", "driving")
MOBILITY_MEASURES = ("km", "minutes")
FILTER_KEYS = ("filter_1", "filter_2", "filter_3")
PROVENANCE = (("source_ids", "source_id"), ("dataset_ids", "dataset_id"), ("license_ids", "license_id"),
              ("attributions", "attribution"), ("usage_restrictions", "usage_restriction"))
CATALOG_COLUMNS = ("catalog_version", "schema_version", "criterion_id", "category", "category_label_pt",
                   "category_label_en", "label_pt", "label_en", "unit", "direction", "methodology_pt", "levels",
                   "modes", "options", "default_range_min", "default_range_max", "weight", "status",
                   "pending_reason", "source_ids", "dataset_ids", "license_ids", "attributions",
                   "usage_restrictions", "reference_periods")
NORMALIZATION_COLUMNS = ("catalog_version", "criterion_id", "level", "variant", "n", "min", "p5", "p95", "max",
                         "is_degenerate")


class CriteriaError(ValueError):
    """Catálogo inválido ou critério `disponivel` sem nenhum valor; a mensagem nomeia o critério ou a categoria."""


def load_criteria(path: Path) -> dict:
    """Lê e valida o YAML; devolve `{"schema_version", "categories", "criteria"}` (ver o contrato)."""
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise CriteriaError(f"catálogo de critérios ilegível em '{path}': {exc}") from exc
    if not isinstance(raw, dict):
        raise CriteriaError(f"catálogo de critérios vazio ou malformado em '{path}'")
    criteria = {"schema_version": raw.get("schema_version"), "categories": raw.get("categories"),
                "criteria": raw.get("criteria")}
    _validate(criteria)
    for item in criteria["criteria"]:
        if item.get("status") == "disponivel":
            _validate_compute(item["id"], item["compute"], parish=False)
        if item.get("compute_parish") is not None:
            _validate_compute(item["id"], item["compute_parish"], parish=True)
            if "freguesia" not in item["levels"]:
                raise CriteriaError(f"critério '{item['id']}': compute_parish exige 'freguesia' em levels")
    return criteria


def _validate(criteria: dict) -> None:
    """Regras estruturais do §1.1 (compartilhadas por `load_criteria` e `catalog_tables`)."""
    if not isinstance(criteria.get("schema_version"), int):
        raise CriteriaError("schema_version ausente ou não inteiro")
    categories, items = criteria.get("categories"), criteria.get("criteria")
    if not isinstance(categories, list) or not categories:
        raise CriteriaError("lista 'categories' ausente ou vazia")
    if not isinstance(items, list) or not items:
        raise CriteriaError("lista 'criteria' ausente ou vazia")
    category_ids: list[str] = []
    for category in categories:
        if not isinstance(category, dict) or not category.get("id"):
            raise CriteriaError(f"categoria sem id: {category!r}")
        for key in ("label_pt", "label_en"):
            if not category.get(key):
                raise CriteriaError(f"categoria '{category['id']}' sem {key}")
        if category["id"] in category_ids:
            raise CriteriaError(f"categoria '{category['id']}' repetida")
        category_ids.append(category["id"])
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or not item.get("id"):
            raise CriteriaError(f"critério sem id: {item!r}")
        _validate_item(item, category_ids, seen)
        seen.add(item["id"])
    for category_id in category_ids:
        _validate_weights(category_id, [item for item in items if item["category"] == category_id])


def _validate_item(item: dict, category_ids: list[str], seen: set[str]) -> None:
    cid = item["id"]
    if cid in seen:
        raise CriteriaError(f"critério '{cid}' repetido")
    if item.get("category") not in category_ids:
        raise CriteriaError(f"critério '{cid}': categoria '{item.get('category')}' não existe em categories")
    for key in ("label_pt", "label_en", "unit", "methodology_pt"):
        if not item.get(key):
            raise CriteriaError(f"critério '{cid}' sem {key}")
    if item.get("direction") not in DIRECTIONS:
        raise CriteriaError(f"critério '{cid}': direction '{item.get('direction')}' inválida")
    for key, allowed in (("levels", LEVELS), ("modes", MODES)):
        values = item.get(key)
        if not isinstance(values, list) or not values or any(value not in allowed for value in values):
            raise CriteriaError(f"critério '{cid}': {key} {values!r} inválido (valores: {', '.join(allowed)})")
    status = item.get("status")
    if status not in STATUSES:
        raise CriteriaError(f"critério '{cid}': status '{status}' inválido")
    if status == "fonte_pendente" and not item.get("pending_reason"):
        raise CriteriaError(f"critério '{cid}': fonte_pendente exige pending_reason")
    if status == "disponivel" and not isinstance(item.get("compute"), dict):
        raise CriteriaError(f"critério '{cid}': disponivel exige compute")
    compute = item.get("compute")
    if compute is not None and (not isinstance(compute, dict) or compute.get("kind") not in KINDS):
        raise CriteriaError(f"critério '{cid}': compute.kind inválido")
    weight = item.get("weight")
    if isinstance(weight, bool) or not isinstance(weight, int | float) or not 0 <= weight <= 1:
        raise CriteriaError(f"critério '{cid}': weight {weight!r} fora de 0 a 1")
    _validate_options(item)
    low, high = _range(item, cid)
    if low is not None and high is not None and low > high:
        raise CriteriaError(f"critério '{cid}': default_range com mínimo maior que o máximo")


def _range(item: dict, cid: str) -> tuple:
    value = item.get("default_range")
    if value is None:
        return None, None
    if not isinstance(value, list | tuple) or len(value) != 2:
        raise CriteriaError(f"critério '{cid}': default_range deve ser [mín, máx]")
    return value[0], value[1]


def _validate_options(item: dict) -> None:
    cid, options = item["id"], item.get("options")
    if "opcao" not in item["modes"]:
        return
    if not isinstance(options, list) or len(options) < 2:
        raise CriteriaError(f"critério '{cid}': o modo opcao exige pelo menos 2 options")
    ids = set()
    for option in options:
        if not isinstance(option, dict) or any(not option.get(key) for key in ("id", "label_pt", "label_en")):
            raise CriteriaError(f"critério '{cid}': option sem id, label_pt ou label_en")
        bounds = option.get("range")
        if not isinstance(bounds, list | tuple) or len(bounds) != 2:
            raise CriteriaError(f"critério '{cid}': option '{option['id']}' sem range [mín, máx]")
        if bounds[0] is not None and bounds[1] is not None and bounds[0] >= bounds[1]:
            raise CriteriaError(f"critério '{cid}': option '{option['id']}' com range vazio")
        if option["id"] in ids:
            raise CriteriaError(f"critério '{cid}': option '{option['id']}' repetida")
        ids.add(option["id"])


def _validate_weights(category_id: str, items: list[dict]) -> None:
    """Pesos > 0 dos critérios disponíveis somam 1; categoria só com pendentes não tem o que pesar."""
    active = [item for item in items if item.get("status") == "disponivel"]
    if not active:
        return
    total = sum(float(item["weight"]) for item in active if item["weight"] > 0)
    if total == 0:
        raise CriteriaError(f"categoria '{category_id}': todos os critérios disponíveis têm peso 0")
    if abs(total - 1) > WEIGHT_TOLERANCE:
        raise CriteriaError(f"categoria '{category_id}': os pesos dos critérios disponíveis somam {total:g}, não 1")


def _validate_compute(cid: str, compute: dict, *, parish: bool) -> None:
    """Campos obrigatórios por `kind` (§1.2); só no carregamento do YAML."""
    kind = compute.get("kind")
    allowed = ("census", "rent") if parish else ("observation", "climate", "mobility", "rent")
    if kind not in allowed:
        where = "compute_parish" if parish else "compute"
        raise CriteriaError(f"critério '{cid}': {where}.kind '{kind}' não permitido (use: {', '.join(allowed)})")
    if kind == "observation":
        _validate_observation(cid, compute)
    elif kind == "climate" and compute.get("metric") not in CLIMATE_METRICS:
        raise CriteriaError(f"critério '{cid}': métrica de clima '{compute.get('metric')}' desconhecida")
    elif kind == "census" and compute.get("metric") not in CENSUS_METRICS:
        raise CriteriaError(f"critério '{cid}': métrica dos Censos '{compute.get('metric')}' desconhecida")
    elif kind == "rent":
        variants = compute.get("variants")
        if compute.get("metric") not in RENT_METRICS:
            raise CriteriaError(f"critério '{cid}': métrica de aluguel '{compute.get('metric')}' desconhecida")
        if not isinstance(variants, list) or not variants or any(v not in TYPOLOGIES for v in variants):
            raise CriteriaError(f"critério '{cid}': variants de aluguel {variants!r} inválidas")
    elif kind == "mobility":
        _validate_mobility(cid, compute)


def _validate_observation(cid: str, compute: dict) -> None:
    for key in ("source_id", "dataset_id"):
        if not compute.get(key):
            raise CriteriaError(f"critério '{cid}': compute.{key} ausente")
    filters = compute.get("filters")
    if not isinstance(filters, list) or not filters or any(not isinstance(part, dict) for part in filters):
        raise CriteriaError(f"critério '{cid}': compute.filters deve ser uma lista de dicts")
    if any(key not in FILTER_KEYS for part in filters for key in part):
        raise CriteriaError(f"critério '{cid}': filtro com chave fora de {', '.join(FILTER_KEYS)}")
    if not isinstance(compute.get("dash_is_zero"), bool):
        raise CriteriaError(f"critério '{cid}': compute.dash_is_zero deve ser true ou false")
    extras = [key for key in ("per_population", "share", "presence") if compute.get(key)]
    if len(extras) > 1:
        raise CriteriaError(f"critério '{cid}': use no máximo um entre per_population, share e presence")
    for key in ("per_population", "share"):
        block = compute.get(key)
        if block is not None and (not isinstance(block, dict) or not isinstance(block.get("scale"), int | float)):
            raise CriteriaError(f"critério '{cid}': compute.{key}.scale ausente")
    share = compute.get("share")
    if share is not None and not isinstance(share.get("filters"), dict):
        raise CriteriaError(f"critério '{cid}': compute.share.filters deve ser um dict")


def _validate_mobility(cid: str, compute: dict) -> None:
    mode, measure = compute.get("mode"), compute.get("measure")
    if mode not in MOBILITY_MODES or measure not in MOBILITY_MEASURES:
        raise CriteriaError(f"critério '{cid}': mobilidade com mode '{mode}' ou measure '{measure}' inválido")
    if measure == "minutes" and mode != "driving":
        raise CriteriaError(f"critério '{cid}': minutes só existe com mode driving")
    if bool(compute.get("pole_id")) == bool(compute.get("nearest_kind")):
        raise CriteriaError(f"critério '{cid}': informe pole_id ou nearest_kind (um dos dois)")


def _values(frame: pd.DataFrame | None, criterion_id: str, level: str) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["variant", "value"])
    rows = frame[(frame["criterion_id"] == criterion_id) & frame["value"].notna()]
    if level == "freguesia" and "origin" in rows.columns:
        rows = rows[rows["origin"] == "proprio"]
    return rows


def _joined(rows: pd.DataFrame, column: str):
    if column not in rows.columns:
        return None
    values = sorted({str(value) for value in rows[column] if value is not None and not pd.isna(value)})
    return " | ".join(values) if values else None


def _plain(value):
    """Valor JSON canônico: numpy vira Python, float com repr, NaN vira nulo."""
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def catalog_version(criteria: dict, normalization: pd.DataFrame) -> str:
    """12 primeiros hex do SHA-256 do JSON canônico das definições e da normalização (sem processed_at_utc)."""
    columns = [column for column in NORMALIZATION_COLUMNS if column != "catalog_version"]
    rows = normalization.sort_values(["criterion_id", "level", "variant"])[columns].to_dict("records")
    body = {"schema_version": criteria["schema_version"], "categories": criteria["categories"],
            "criteria": criteria["criteria"], "normalizacao": rows}
    text = json.dumps(_plain(body), sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def catalog_tables(criteria: dict, indicators: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Valida o catálogo contra os indicadores calculados e devolve `(catalogo, normalizacao)`.

    `indicators` mapeia o nível (`municipio`, `freguesia`) para a tabela longa de indicadores desse nível.
    Levanta `CriteriaError` se um critério `disponivel` não tiver valor ou se os pesos de uma categoria não
    somarem 1. As duas tabelas levam a mesma `catalog_version`, que muda com qualquer definição ou parâmetro.
    """
    _validate(criteria)
    labels = {category["id"]: category for category in criteria["categories"]}
    normalization_rows, catalog_rows = [], []
    for item in criteria["criteria"]:
        used = []
        if item["status"] == "disponivel":
            for level in item["levels"]:
                if level not in indicators:
                    continue  # nível ainda não construído (a freguesia é opcional até a P3)
                rows = _values(indicators[level], item["id"], level)
                if rows.empty:
                    raise CriteriaError(f"critério '{item['id']}' está disponivel mas não tem nenhum valor no nível "
                                        f"'{level}' (FR-020): corrija a fonte ou marque-o como fonte_pendente")
                used.append(rows)
                for variant, group in rows.groupby(rows["variant"].fillna(""), sort=True):
                    values = group["value"].astype(float).to_numpy()
                    p5, p95 = np.percentile(values, [5, 95])
                    normalization_rows.append({
                        "criterion_id": item["id"], "level": level, "variant": str(variant), "n": len(values),
                        "min": float(values.min()), "p5": float(p5), "p95": float(p95),
                        "max": float(values.max()), "is_degenerate": bool(p5 == p95)})
        rows = pd.concat(used, ignore_index=True) if used else pd.DataFrame()
        low, high = _range(item, item["id"])
        category = labels[item["category"]]
        periods = sorted({str(value) for value in rows.get("period", pd.Series(dtype=object)) if value is not None
                          and not pd.isna(value)})
        catalog_rows.append({
            "schema_version": int(criteria["schema_version"]), "criterion_id": item["id"],
            "category": item["category"], "category_label_pt": category["label_pt"],
            "category_label_en": category["label_en"], "label_pt": item["label_pt"], "label_en": item["label_en"],
            "unit": item["unit"], "direction": item["direction"], "methodology_pt": item["methodology_pt"],
            "levels": json.dumps(item["levels"], ensure_ascii=False),
            "modes": json.dumps(item["modes"], ensure_ascii=False),
            "options": json.dumps(_plain(item["options"]), ensure_ascii=False) if item.get("options") else None,
            "default_range_min": None if low is None else float(low),
            "default_range_max": None if high is None else float(high),
            "weight": float(item["weight"]), "status": item["status"], "pending_reason": item.get("pending_reason"),
            **{target: _joined(rows, column) for target, column in PROVENANCE},
            "reference_periods": json.dumps(periods, ensure_ascii=False) if periods else None})
    normalization = pd.DataFrame(normalization_rows,
                                 columns=[c for c in NORMALIZATION_COLUMNS if c != "catalog_version"])
    version = catalog_version(criteria, normalization)
    normalization.insert(0, "catalog_version", version)
    catalog = pd.DataFrame(catalog_rows)
    catalog.insert(0, "catalog_version", version)
    return catalog[list(CATALOG_COLUMNS)], normalization
