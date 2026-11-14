"""Associação territorial explícita."""

import pandas as pd


def align_censos(
    observations: pd.DataFrame,
    parishes: pd.DataFrame,
    crosswalk: pd.DataFrame,
    *,
    categories: pd.DataFrame,
    target_version: str,
) -> pd.DataFrame:
    """Uma observação por destino/categoria, com herança e ausência explícitas."""
    if (
        set(parishes.caop_version.astype(str)) != {target_version}
        or parishes.dicofre.duplicated().any()
    ):
        raise ValueError("dimensão territorial/versão inválida")
    if not set(observations.geography_version.astype(str)) <= {"2013", target_version}:
        raise ValueError("origem territorial não suportada")
    keys = ["geography_version", "source_dicofre", "age_code"]
    if observations.duplicated(keys).any():
        raise ValueError("observações duplicadas/conflitantes de mesma precedência")
    indexed = {
        (str(r["geography_version"]), r["source_dicofre"], r["age_code"]): r
        for r in observations.to_dict("records")
    }
    pairs = {code: group for code, group in crosswalk.groupby("dicofre_2025")}
    statuses = {
        "suppressed": "official_suppression",
        "not_applicable": "official_not_applicable",
        "not_published": "official_not_published",
    }
    rows = []
    for parish in parishes.to_dict("records"):
        for category in categories.to_dict("records"):
            code, age = parish["dicofre"], category["age_code"]
            origin = indexed.get((target_version, code, age))
            official_unavailable = (
                origin
                if origin is not None and origin["value_status"] == "not_published"
                else None
            )
            relation = "direct"
            inherited = False
            reason = None
            if origin is not None and origin["value_status"] == "not_published":
                # Explicit official unavailability permits fallback; suppression never does.
                origin = None
            if origin is None:
                group = pairs.get(code)
                if target_version != "2025" and group is not None:
                    raise ValueError("correspondência só suporta destino 2025")
                if group is not None:
                    partial = group.partial_origin.any()
                    if (
                        partial
                        or len(group) != 1
                        or group.relation.isin(["many_to_many", "many_to_one"]).any()
                    ):
                        reason = "territorial_ambiguity"
                    else:
                        pair = group.iloc[0]
                        relation = pair.relation
                        origin = indexed.get(("2013", pair.dicofre_2013, age))
                        inherited = relation == "one_to_many"
                if origin is None and reason is None:
                    reason = "missing_source"
            if (
                origin is None
                and official_unavailable is not None
                and reason == "missing_source"
            ):
                origin = official_unavailable
                relation = "direct"
                inherited = False
            region = parish.get("autonomous_region")
            row = {
                **category,
                **(origin or {}),
                "dicofre": code,
                "dico": parish["dico"],
                "caop_version": target_version,
                "autonomous_region": "continente"
                if region is None or pd.isna(region)
                else region,
                "coverage_status": "missing",
                "reason": reason,
                "relation": relation,
                "partial_origin": reason == "territorial_ambiguity",
            }
            if origin is not None:
                status = origin["value_status"]
                row.update(
                    coverage_status=("inherited" if inherited else "own")
                    if status == "observed"
                    else "missing",
                    reason=statuses.get(status),
                    value=origin["value"],
                )
            else:
                row.update(
                    value=None, value_status="not_published", source_dicofre=None
                )
            rows.append(row)
    result = pd.DataFrame(rows)
    destinations = set(parishes.dicofre)
    legacy = set(crosswalk.dicofre_2013)
    orphans = observations[
        (
            observations.geography_version.astype(str).eq(target_version)
            & ~observations.source_dicofre.isin(destinations)
        )
        | (
            observations.geography_version.astype(str).eq("2013")
            & ~observations.source_dicofre.isin(legacy)
        )
    ]
    if (
        not orphans.empty
        and not orphans.source_dicofre.str[:4].isin(set(parishes.dico)).all()
    ):
        raise ValueError("município da origem não resolvido")
    result.attrs["orphans"] = orphans.to_dict("records")
    result["value"] = result.value.astype("Int64")
    return result
