"""Fronteira pública da leitura censitária."""

import json
from pathlib import Path

import pandas as pd

from pipelines.collectors.censos2021.validate import (
    age_categories,
    check_document,
    load_document,
    parse_count,
    selected_ages,
    validate_censos_response,
)


def read_censos_response(dataset: dict, path: Path, metadata: dict) -> pd.DataFrame:
    """Contagens e limites etários oficiais; nenhuma imputação."""
    validate_censos_response(dataset, path)
    check_document(dataset, metadata)
    ages = age_categories(metadata).set_index("age_code")
    if not set(selected_ages(dataset)) <= set(ages.index):
        raise ValueError("categoria selecionada não consta dos metadados")
    rows = []
    for row in load_document(path)["Dados"]["2021"]:
        info = ages.loc[row["dim_4"]].to_dict()
        value, status, symbol = parse_count(row)
        rows.append(
            {
                "source_dicofre": row["geocod"],
                "period": "2021",
                "age_code": row["dim_4"],
                **info,
                "value": value,
                "value_status": status,
                "symbol": symbol,
                "indicator": dataset["indicator"],
                "geography_version": dataset["geography_version"],
                "dataset_id": dataset["id"],
            }
        )
    result = pd.DataFrame(rows)
    result["value"] = result["value"].astype("Int64")
    return result


def canonical_code(row):
    if row["is_total"]:
        return "T"
    if row.get("is_unknown", False):
        return "unknown"
    lo, hi = int(row["age_min"]), row["age_max"]
    return f"{lo}_plus" if pd.isna(hi) else f"{lo}_{int(hi)}"


def harmonize_age_categories(observations, categories):
    """Harmoniza limites; conserva referências de todas as linhas que originaram uma faixa."""
    frame = observations.copy()
    frame["age_code"] = frame.apply(canonical_code, axis=1)
    frame["source_age_codes"] = observations["age_code"].map(lambda x: json.dumps([x]))
    older = frame.age_code.isin(["85_89", "90_plus"])
    if not older.any():
        return frame
    merged = []
    for _, group in frame[older].groupby(
        ["source_dicofre", "period", "geography_version", "indicator"], dropna=False
    ):
        if set(group.age_code) != {"85_89", "90_plus"} or len(group) != 2:
            raise ValueError("faixa 85+ legada incompleta")
        row = group.iloc[0].to_dict()
        observed = group.value_status.eq("observed").all()
        row.update(
            age_code="85_plus",
            age_min=85,
            age_max=None,
            value=int(group.value.sum()) if observed else None,
            value_status="observed"
            if observed
            else "suppressed"
            if group.value_status.eq("suppressed").any()
            else group.loc[group.value_status.ne("observed"), "value_status"].iloc[0],
            source_age_codes=json.dumps(
                [x for s in group.source_age_codes for x in json.loads(s)]
            ),
        )
        for field in (
            "dataset_id",
            "raw_key",
            "raw_sha256",
            "source_run_id",
            "collected_at_utc",
        ):
            if field in group:
                row[field] = json.dumps(group[field].tolist())
        merged.append(row)
    return pd.concat([frame[~older], pd.DataFrame(merged)], ignore_index=True)
