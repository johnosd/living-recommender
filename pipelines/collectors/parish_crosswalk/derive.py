"""Derivação da correspondência 2013→2025 (spec 004, FR-007 a FR-011 e FR-014).

Regras em `sdd/specs/004-correspondencia-freguesias/logic/derivacao-correspondencia.md` §3 e `research.md` R4.
"""

import numpy as np
import pandas as pd

from pipelines.collectors.parish_crosswalk.layout import normalize_label

CROSSWALK_COLUMNS = [
    "dicofre_2013", "name_2013", "dicofre_2025", "name_2025", "relation", "inherited",
    "partial_origin", "name_changed", "municipality_changed", "pre2013_codes",
]
TABLE_A_REQUIRED = ["pre_code", "name_2013", "code_2013", "partial_origin"]
TABLE_B_REQUIRED = ["pre_code", "code_2025", "name_2025"]


class CrosswalkDerivationError(ValueError):
    """As tabelas do INE são inconsistentes entre si e a correspondência não pode ser derivada."""


def _require(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise CrosswalkDerivationError(f"tabela {label} sem colunas: {', '.join(missing)}")


def _single_value(frame: pd.DataFrame, key: list[str], column: str, what: str) -> None:
    """Cada chave deve ter uma só designação; duas designações para o mesmo código é inconsistência da fonte."""
    counts = frame.groupby(key)[column].nunique()
    bad = counts[counts > 1]
    if len(bad):
        codes = ", ".join("/".join(map(str, index if isinstance(index, tuple) else (index,))) for index in bad.index[:10])
        raise CrosswalkDerivationError(f"{what} com mais de uma designação: {codes}")


def derive_parish_crosswalk(table_a: pd.DataFrame, table_b: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por par (dicofre_2013, dicofre_2025), ordenada e determinística.

    A tabela A liga cada freguesia pré-2013 ao código de 2013; a B, as 302 repostas ao código de 2025. Uma
    freguesia pré-2013 que não consta na B mantém em 2025 o código e a designação de 2013.
    """
    _require(table_a, TABLE_A_REQUIRED, "A")
    _require(table_b, TABLE_B_REQUIRED, "B")
    if table_a.empty:
        raise CrosswalkDerivationError("tabela A sem linhas")
    unknown = sorted(set(table_b["pre_code"]) - set(table_a["pre_code"]))
    if unknown:
        raise CrosswalkDerivationError(f"a tabela B repõe freguesias que a A não conhece: {', '.join(unknown[:10])}")
    repeated = table_b["pre_code"][table_b["pre_code"].duplicated()].unique()
    if len(repeated):
        raise CrosswalkDerivationError(f"a tabela B repete freguesias pré-2013: {', '.join(sorted(repeated)[:10])}")
    _single_value(table_a, ["code_2013"], "name_2013", "código de 2013")

    # Granularidade da linha da A: o mesmo código pré-2013 pode aparecer duas vezes ("(parte)").
    chain = table_a[TABLE_A_REQUIRED].merge(table_b[TABLE_B_REQUIRED], on="pre_code", how="left")
    chain["dicofre_2025"] = chain["code_2025"].fillna(chain["code_2013"])
    chain["name_2025"] = chain["name_2025"].fillna(chain["name_2013"])
    _single_value(chain, ["code_2013", "dicofre_2025"], "name_2025", "par (2013, 2025)")

    pairs = (
        chain.groupby(["code_2013", "dicofre_2025"], sort=True)
        .agg(
            name_2013=("name_2013", "first"),
            name_2025=("name_2025", "first"),
            partial_origin=("partial_origin", "any"),
            pre2013_codes=("pre_code", lambda codes: sorted(set(codes))),
        )
        .reset_index()
        .rename(columns={"code_2013": "dicofre_2013"})
    )
    destinations = pairs.groupby("dicofre_2013")["dicofre_2025"].transform("nunique")
    origins = pairs.groupby("dicofre_2025")["dicofre_2013"].transform("nunique")
    pairs["relation"] = np.select(
        [(destinations == 1) & (origins == 1), (destinations > 1) & (origins == 1), (destinations == 1) & (origins > 1)],
        ["one_to_one", "one_to_many", "many_to_one"],
        default="many_to_many",
    )
    pairs["inherited"] = (destinations > 1).astype(bool)
    pairs["partial_origin"] = pairs["partial_origin"].astype(bool)
    pairs["name_changed"] = [
        normalize_label(old) != normalize_label(new) for old, new in zip(pairs["name_2013"], pairs["name_2025"])
    ]
    pairs["municipality_changed"] = pairs["dicofre_2013"].str[:4] != pairs["dicofre_2025"].str[:4]
    return pairs[CROSSWALK_COLUMNS].sort_values(["dicofre_2013", "dicofre_2025"]).reset_index(drop=True)
