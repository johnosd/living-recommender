"""Indicadores de distância e tempo de viagem a partir de `stg_municipality_pole_distance` (spec 009).

Regras (polo fixo ou mais próximo, pares que falharam, atribuição do Google):
`.sdd/specs/011-marts-indicadores-catalogo/logic/indicadores.md` §2.
"""
import pandas as pd

from pipelines.gold.common import available, indicator_frame, indicator_row

DATASET_ID = "stg_municipality_pole_distance"
NOT_OK = {"falha": "par_falha", "pendente": "par_pendente"}


def _provenance(pair: dict) -> dict:
    period = pair.get("reference_period")
    return {"source_id": pair.get("source_id"), "dataset_id": DATASET_ID, "license_id": pair.get("license_id"),
            "attribution": pair.get("attribution"), "usage_restriction": pair.get("usage_restriction"),
            "period": period, "dataset_latest_period": period, "is_older_period": False,
            "is_stale": bool(pair.get("stale") or False)}


def _choose(pairs: list[dict], compute: dict) -> tuple[dict | None, str | None]:
    """(par escolhido, motivo de ausência): nunca troca um par que falhou por outro (FR-007)."""
    if not pairs:
        return None, "sem_par_elegivel"
    failed = [pair for pair in pairs if pair["status"] in NOT_OK]
    if failed:  # o par que falhou poderia ser o mais próximo
        return None, NOT_OK[min(failed, key=lambda pair: pair["pole_id"])["status"]]
    measure = compute["measure"]
    ok = [pair for pair in pairs if pair["status"] == "ok" and pair.get(measure) is not None
          and not pd.isna(pair.get(measure))]
    if not ok:
        return None, "sem_rota"
    return min(ok, key=lambda pair: (float(pair[measure]), pair["pole_id"])), None


def mobility_indicators(distances: pd.DataFrame, poles: pd.DataFrame, municipalities: pd.DataFrame,
                        criteria: dict) -> pd.DataFrame:
    """Uma linha por município x critério disponível com `compute.kind == "mobility"`."""
    kinds = dict(zip(poles["pole_id"], poles["kind"], strict=True))
    by_key: dict[tuple, list[dict]] = {}
    by_mode: dict[str, dict] = {}  # proveniência da fonte do modo, para ausências sem par
    for pair in distances.to_dict("records"):
        by_key.setdefault((pair["dico"], pair["mode"]), []).append(pair)
        by_mode.setdefault(pair["mode"], pair)
    rows = []
    for criterion in available(criteria, "mobility"):
        compute = criterion["compute"]
        for dico in municipalities["dico"]:
            candidates = by_key.get((dico, compute["mode"]), [])
            if compute.get("pole_id"):
                pairs = [pair for pair in candidates if pair["pole_id"] == compute["pole_id"]]
            else:
                pairs = [pair for pair in candidates if kinds.get(pair["pole_id"]) == compute["nearest_kind"]]
            chosen, reason = _choose(pairs, compute)
            if chosen is None:
                reference = min(pairs, key=lambda pair: pair["pole_id"]) if pairs else by_mode.get(compute["mode"])
                provenance = _provenance(reference) if reference else {"dataset_id": DATASET_ID}
                provenance["is_stale"] = bool(pairs) and provenance.get("is_stale", False)
                rows.append(indicator_row(dico, criterion, value=None, missing_reason=reason, **provenance))
                continue
            rows.append(indicator_row(dico, criterion, value=float(chosen[compute["measure"]]),
                                      value_status="observado", **_provenance(chosen)))
    return indicator_frame(rows)
