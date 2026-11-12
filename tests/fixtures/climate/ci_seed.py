"""Fixture climática nacional, sempre offline, coletada pelo próprio handler."""
import argparse
import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yaml

from pipelines.cli.build_climate import PROMOTED, prepare_climate
from pipelines.collectors._shared.catalog import get_climate_source, load_catalog
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors.open_meteo.handler import collect_open_meteo
from tests.fixtures.open_meteo.responses import municipalities, open_meteo_response


def response(item):
    doc = json.loads(open_meteo_response(start=item["window"]["start"], end=item["window"]["end"],
                                        latitude=item["latitude"], longitude=item["longitude"]))
    size = len(doc["daily"]["time"])
    for prefix in ("temperature_2m", "apparent_temperature"):
        for suffix, value in [("min", 10), ("mean", 15), ("max", 20)]:
            doc["daily"][f"{prefix}_{suffix}"] = [value + (i % 20) * .1 for i in range(size)]
    return json.dumps(doc, ensure_ascii=False)


def seed(root, *, days=31, prepare=True, collected=308, gaps=0, diverged=False):
    root = Path(root)
    towns = municipalities(308)
    path = root / "lake/silver/dim_municipality/data.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(towns).rename(columns={"name": "official_name", "latitude": "representative_lat",
                                       "longitude": "representative_lon"}).to_parquet(path, index=False)
    source = get_climate_source(load_catalog())
    start = date(2025, 1, 1)
    source["window"] = {"start": start.isoformat(), "end": (start+timedelta(days=days-1)).isoformat()}
    catalog = {"open_meteo": source}
    (root / "catalog.yml").write_text(yaml.safe_dump({"sources": catalog}, allow_unicode=True), encoding="utf-8")

    def fetch(item, destination):
        doc = json.loads(response(item))
        if int(item["id"]) <= gaps:
            doc["daily"]["precipitation_sum"][1] = None
        if diverged and item["id"] == "0001":
            doc["latitude"] += .36
            doc["elevation"] = 0
        destination.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    collect_open_meteo(catalog, municipalities=towns, storage=LocalStorage(root), fetcher=fetch,
                       run_id="ci-climate", collected_at_utc="2026-11-11T12:00:00Z",
                       work_dir=root / ".work/climate", max_municipalities=collected)
    for relative in PROMOTED:
        (root / relative).mkdir(parents=True, exist_ok=True)
    result = {"catalog": catalog, "towns": towns}
    if prepare:
        result.update(prepare_climate(root, root / "prepared", processed_at_utc="2026-11-11T13:00:00Z", catalog=catalog))
    return result


def main():
    parser = argparse.ArgumentParser(description="Gera clima sintético e Silver para testes offline.")
    parser.add_argument("--root", type=Path, default=Path(".data/ci-climate"))
    parser.add_argument("--days", type=int, default=31)
    args = parser.parse_args()
    if args.days < 2:
        parser.error("--days precisa ser pelo menos 2")
    if args.root.exists() and any(args.root.iterdir()):
        parser.error(f"{args.root} já existe e não está vazio; use outro --root")
    result = seed(args.root, days=args.days)
    print({k: v for k, v in result.items() if k not in ("catalog", "towns")})


if __name__ == "__main__":
    main()
