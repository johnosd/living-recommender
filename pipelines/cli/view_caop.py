"""Gera uma visão local e CSVs das dimensões Silver da CAOP."""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


class ViewError(ValueError):
    """Dimensões Silver ausentes ou inconsistentes para visualização."""


def _records(frame: pd.DataFrame, columns: list[str]) -> list[dict]:
    selected = frame[columns].astype(object).where(pd.notna(frame[columns]), None)
    return selected.to_dict(orient="records")


def generate_view(root: Path = Path(".data")) -> dict[str, Path]:
    """Cria HTML autônomo e CSVs de municípios/freguesias a partir da Silver."""
    root = Path(root).resolve()
    municipalities_path = root / "lake" / "silver" / "dim_municipality" / "data.parquet"
    parishes_path = root / "lake" / "silver" / "dim_parish" / "data.parquet"
    if not municipalities_path.is_file() or not parishes_path.is_file():
        raise ViewError("Silver ausente; execute python -m pipelines.cli.build_caop primeiro")
    municipalities = pd.read_parquet(municipalities_path)
    parishes = pd.read_parquet(parishes_path)
    if municipalities.empty or parishes.empty or not set(parishes.dico).issubset(set(municipalities.dico)):
        raise ViewError("dimensões vazias ou freguesias sem município")
    if len(set(municipalities.source_run_id) | set(parishes.source_run_id)) != 1:
        raise ViewError("dimensões de coletas diferentes")
    output = root / "explore"
    output.mkdir(parents=True, exist_ok=True)
    municipalities_csv = output / "municipios.csv"
    parishes_csv = output / "freguesias.csv"
    municipalities.to_csv(municipalities_csv, sep=";", index=False, encoding="utf-8-sig")
    parishes.to_csv(parishes_csv, sep=";", index=False, encoding="utf-8-sig")
    payload = {
        "run_id": str(municipalities.source_run_id.iloc[0]),
        "version": str(municipalities.caop_version.iloc[0]),
        "processed_at_utc": str(municipalities.processed_at_utc.iloc[0]),
        "municipalities": _records(
            municipalities,
            ["dico", "official_name", "district_or_island", "autonomous_region", "area_km2"],
        ),
        "parishes": _records(parishes, ["dicofre", "dico", "official_name", "area_km2"]),
    }
    serialized = json.dumps(payload, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
    template = Path(__file__).with_name("caop_explorer.html").read_text(encoding="utf-8")
    html = output / "caop.html"
    html.write_text(template.replace("__CAOP_DATA__", serialized), encoding="utf-8")
    return {"html": html, "municipalities_csv": municipalities_csv, "parishes_csv": parishes_csv}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera explorador HTML e CSVs da CAOP Silver.")
    parser.add_argument("--root", type=Path, default=Path(".data"), help="raiz local")
    args = parser.parse_args(argv)
    try:
        paths = generate_view(args.root)
    except (ViewError, OSError, KeyError, ValueError) as exc:
        print(f"CAOP view: falha: {exc}", file=sys.stderr)
        return 1
    print(f"Abra no navegador: {paths['html']}")
    print(f"Abra no Excel: {paths['municipalities_csv']} e {paths['parishes_csv']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
