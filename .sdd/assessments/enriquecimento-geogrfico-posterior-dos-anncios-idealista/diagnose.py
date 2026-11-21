"""Triagem offline; não geocodifica nem altera anúncios ou atribuições territoriais."""

import collections
import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path

import pandas as pd


def norm(value):
    decomposed = unicodedata.normalize("NFKD", " ".join(value.split()))
    return "".join(char for char in decomposed if not unicodedata.combining(char)).lower()


def main():
    root = Path(".data")
    summary = json.loads((root / "lake/bronze/idealista_reports/summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / f"manifests/idealista/{summary['source_run_id']}.json").read_text(encoding="utf-8"))
    municipalities = pd.read_parquet(root / "lake/silver/dim_municipality/data.parquet")
    parishes = pd.read_parquet(root / "lake/silver/dim_parish/data.parquet")
    listings = pd.read_parquet(root / "lake/silver/idealista_listings/data.parquet").set_index("listing_id")
    municipal_district = {row.dico: norm(row.district_or_island) for row in municipalities.itertuples()}
    parish_names, municipal_names = collections.defaultdict(set), collections.defaultdict(set)
    for row in parishes.itertuples():
        parish_names[(municipal_district[row.dico], norm(row.official_name))].add((row.dico, row.dicofre))
    with Path("analytics/dbt/seeds/idealista_metadata_parish_synonyms.csv").open(encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            parish_names[(municipal_district[row["dico"]], norm(row["source_name"]))].add((row["dico"], row["dicofre"]))
    for row in municipalities.itertuples():
        municipal_names[(norm(row.district_or_island), norm(row.official_name))].add(row.dico)
    islands = {"Madeira (Ilha)": "Ilha da Madeira", "Porto Santo (Ilha)": "Ilha de Porto Santo",
               "São Miguel (Ilha dos Açores)": "Ilha de São Miguel", "Terceira (Ilha dos Açores)": "Ilha Terceira"}
    counts = collections.Counter()
    by_district = collections.defaultdict(collections.Counter)
    candidate_municipalities, unique_queries = set(), set()
    for entry in manifest["files"]:
        data = (root / entry["key"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]
        for row in json.loads(data.decode("utf-8-sig")):
            title = row.get("Titulo") or ""
            street = bool(re.search(r"\b(rua|avenida|travessa|estrada|largo|praça|praca|alameda|urbaniza\w*|caminho)\b", title, re.IGNORECASE))
            counts["total"] += 1
            counts["street_mention"] += street
            counts["postal_code_mention"] += bool(re.search(r"\b\d{4}-\d{3}\b", title))
            if pd.notna(listings.loc[str(row["id"]), "dico"]):
                continue
            counts["regional"] += 1
            counts["regional_street_mention"] += street
            district = norm(islands.get(row.get("Sub-região"), row.get("Sub-região") or ""))
            names = {norm(row["Freguesia"])} if row.get("Freguesia") else set()
            if "," in title:
                names.add(norm(title.rsplit(",", 1)[1]))
            candidates, dicofres = set(), set()
            for name in names:
                matched = parish_names.get((district, name), set())
                candidates.update(dico for dico, _ in matched)
                dicofres.update(dicofre for _, dicofre in matched)
                candidates.update(municipal_names.get((district, name), set()))
            bucket = ("unique_municipality_candidate" if len(candidates) == 1
                      else "ambiguous_candidates" if candidates else "no_exact_candidate")
            counts[bucket] += 1
            by_district[row.get("Sub-região") or "não informado"][bucket] += 1
            if len(candidates) == 1:
                candidate_municipalities.update(candidates)
                counts["unique_parish_candidate"] += len(dicofres) == 1
            unique_queries.add((title, row.get("Sub-região")))
    assert counts["total"] == summary["records"]
    assert counts["regional"] == sum(counts[key] for key in (
        "unique_municipality_candidate", "ambiguous_candidates", "no_exact_candidate"))
    result = {"kind": "Exploratory offline matching; no geocoder and no accepted territorial assignments",
              "snapshot_month": summary["snapshot_month"], "source_run_id": summary["source_run_id"],
              "snapshot_sha256": summary["snapshot_sha256"], "raw_hashes_verified": len(manifest["files"]),
              "counts": dict(counts), "regional_candidate_municipalities": len(candidate_municipalities),
              "regional_distinct_title_contexts": len(unique_queries), "by_district": dict(by_district),
              "limitations": ["Street mention is not a complete address.",
                              "A unique name candidate has not been manually validated.",
                              "No source/lake changes or external geocoding calls.",
                              "Provider accuracy and actual recovered coverage remain unmeasured."]}
    output = Path(__file__).with_name("diagnostic.json")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"]))


if __name__ == "__main__":
    main()
