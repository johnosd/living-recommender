"""Fixture de mobilidade, sempre offline: Silver mínima, polos, catálogo e, opcionalmente, pares coletados."""
import argparse
from pathlib import Path

import pandas as pd
import yaml

from tests.fixtures.mobility.responses import (
    COLLECTED_AT,
    catalog,
    municipalities,
    raw_poles,
    routes_element_error,
    routes_not_found,
    routes_ok,
)


def seed(root, *, collect=False, max_elements=100):
    """Grava `lake/silver/dim_municipality`, `poles.yml` e `catalog.yml` em `root`; com `collect`, coleta pares
    sintéticos (ok, sem_rota e falha) pelo próprio coletor, sem rede."""
    root = Path(root)
    towns = municipalities()
    path = root / "lake/silver/dim_municipality/data.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{
        "dico": town["dico"], "official_name": town["name"], "representative_lat": town["latitude"],
        "representative_lon": town["longitude"], "district_or_island": town["district_or_island"],
        "autonomous_region": town["autonomous_region"], "caop_version": "fixture-2025",
        "license_id": "CC-BY-4.0",
    } for town in towns]).to_parquet(path, index=False)
    (root / "poles.yml").write_text(yaml.safe_dump({"version": 1, "poles": raw_poles()}, allow_unicode=True),
                                    encoding="utf-8")
    fixture_catalog = catalog(max_elements=max_elements)
    (root / "catalog.yml").write_text(yaml.safe_dump(fixture_catalog, allow_unicode=True), encoding="utf-8")
    result = {"catalog": fixture_catalog, "towns": towns}
    if collect:
        from pipelines.collectors._shared.storage import LocalStorage
        from pipelines.collectors.mobility.handler import collect_mobility
        from pipelines.collectors.mobility.poles import resolve_poles

        poles = resolve_poles(raw_poles(), towns)

        def fetch(item, destination):
            if item["id"].startswith("0201"):
                body = routes_not_found()
            elif item["id"].startswith("0102--aeroporto_x--driving"):
                body = routes_element_error()
            else:
                body = routes_ok()
            destination.write_text(body, encoding="utf-8")

        collect_mobility(fixture_catalog, municipalities=towns, poles=poles, storage=LocalStorage(root),
                         fetcher=fetch, run_id="ci-mobility", collected_at_utc=COLLECTED_AT,
                         work_dir=root / ".work/mobility")
    return result


def main():
    parser = argparse.ArgumentParser(description="Gera a Silver e os catálogos sintéticos da mobilidade (offline).")
    parser.add_argument("--root", type=Path, default=Path(".data/ci-mobility"))
    parser.add_argument("--collect", action="store_true", help="coleta pares sintéticos pelo coletor")
    args = parser.parse_args()
    if args.root.exists() and any(args.root.iterdir()):
        parser.error(f"{args.root} já existe e não está vazio; use outro --root")
    seed(args.root, collect=args.collect)
    print(f"fixture de mobilidade em {args.root}")


if __name__ == "__main__":
    main()
