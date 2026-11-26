"""Mart de qualidade: cobertura, período anterior, zeros por convenção, `stale`, outliers e pendentes (spec 011, US2).

Uma linha por critério do catálogo × nível declarado × variante (`data-model.md`, `gold_data_quality`). Cobertura é
só o valor próprio, nos dois níveis; os herdados são contados à parte, pelo nível de origem (spec 012, FR-014).
"""
import json

import pandas as pd

KEYS = {"municipio": "dico", "freguesia": "dicofre"}
INHERITED_COLUMNS = {"inherited_municipio": "municipio", "inherited_distrito": "distrito",
                     "inherited_regiao": "regiao"}
COUNT_COLUMNS = ("territories_expected", "with_value", "missing", "zero_by_convention", "older_period", "inherited",
                 *INHERITED_COLUMNS, "stale", "outliers")
COLUMNS = ("catalog_version", "criterion_id", "level", "variant", "status", *COUNT_COLUMNS, "dataset_latest_period",
           "pending_reason")


def _expected(frame: pd.DataFrame, level: str) -> int:
    key = KEYS[level]
    return int(frame[key].nunique()) if key in frame.columns and not frame.empty else 0


def _outliers(rent: pd.DataFrame | None, variant: str) -> int:
    if rent is None or rent.empty:
        return 0
    return int(rent.loc[rent["typology"] == variant, "n_outliers"].sum())


def _split(group: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """As linhas de valor próprio e a contagem dos herdados (total e por nível de origem)."""
    if "origin" not in group.columns:  # perfil sem herança: tudo é próprio
        return group, {"inherited": 0}
    inherited = group[group["origin"] == "herdado"]
    counts = {"inherited": len(inherited)}
    if "origin_level" in inherited.columns:
        counts.update({column: int((inherited["origin_level"] == level).sum())
                       for column, level in INHERITED_COLUMNS.items()})
    return group[group["origin"] == "proprio"], counts


def _row(version, criterion_id, level, variant, status, **counts) -> dict:
    row = {column: 0 for column in COLUMNS}
    row.update(catalog_version=version, criterion_id=criterion_id, level=level, variant=variant, status=status,
               dataset_latest_period=None, pending_reason=None)
    row.update(counts)
    return row


def data_quality(catalog: pd.DataFrame, indicators_by_level: dict[str, pd.DataFrame],
                 rent_by_level: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Contagens de qualidade por critério × nível × variante; os pendentes saem com cobertura 0 e o motivo."""
    rows = []
    for item in catalog.to_dict("records"):
        version, criterion_id, levels = item["catalog_version"], item["criterion_id"], json.loads(item["levels"])
        if item["status"] != "disponivel":
            for level in levels:
                rows.append(_row(version, criterion_id, level, "", item["status"],
                                 pending_reason=f"fonte pendente: {item['pending_reason']}"))
            continue
        for level in levels:
            frame = indicators_by_level.get(level)
            if frame is None:
                continue  # nível ainda não construído
            expected = _expected(frame, level)
            subset = frame[frame["criterion_id"] == criterion_id]
            for variant, group in subset.groupby(subset["variant"].fillna(""), sort=True):
                own, inherited = _split(group)
                with_value = int(own["value"].notna().sum())
                is_rent = (group["source_id"] == "idealista").any()
                rows.append(_row(
                    version, criterion_id, level, str(variant), item["status"], territories_expected=expected,
                    with_value=with_value, missing=expected - with_value,
                    zero_by_convention=int((own["value_status"] == "zero_convencao_fonte").sum()),
                    older_period=int(own["is_older_period"].sum()),
                    **inherited, stale=int(own["is_stale"].sum()),
                    outliers=_outliers(rent_by_level.get(level), str(variant)) if is_rent else 0,
                    dataset_latest_period=group["dataset_latest_period"].dropna().max() if
                    group["dataset_latest_period"].notna().any() else None))
    frame = pd.DataFrame(rows, columns=list(COLUMNS))
    for column in COUNT_COLUMNS:
        frame[column] = frame[column].astype("int64")
    return frame
