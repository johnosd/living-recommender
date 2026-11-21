"""Normalização e resolução territorial de snapshots manuais."""

import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

from pipelines.collectors._shared.manifest import file_digest
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors.idealista.normalize import normalize_listing
from pipelines.collectors.idealista.snapshot import (
    IdealistaError,
    latest_snapshot,
    read_rows,
)
from pipelines.collectors.idealista.territory import TerritoryResolver

BASE_COLUMNS = [
    "listing_id", "source_id", "snapshot_month", "dico", "dicofre", "locality_level", "locality_raw",
    "source_region", "parish_match_method", "asking_rent_eur", "area_m2", "bedrooms", "typology", "quality_flags",
    "source_run_id", "raw_key", "raw_sha256", "relative_path", "source_row", "collected_at_utc",
    "imported_at_utc", "processed_at_utc", "license_id", "attribution",
]
CONFLICT_COLUMNS = ("asking_rent_eur", "area_m2", "bedrooms", "dico", "dicofre")


def _typed(frame):
    for column in frame.columns:
        if column in ("asking_rent_eur", "area_m2"):
            frame[column] = frame[column].astype("Float64")
        elif column in ("bedrooms", "source_row", "occurrence_count", "duplicate_count"):
            frame[column] = frame[column].astype("Int64")
        elif column == "has_conflict":
            frame[column] = frame[column].astype(bool)
        else:
            frame[column] = frame[column].astype("string")
    return frame


def _unique(occurrences):
    groups = defaultdict(list)
    for row in occurrences.to_dict("records"):
        groups[row["listing_id"]].append(row)
    rows = []
    for identity in sorted(groups):
        group = groups[identity]
        chosen = dict(group[0])
        conflicts = []
        if len(group) > 1:
            conflicts = [column for column in CONFLICT_COLUMNS
                         if len({None if pd.isna(row[column]) else row[column] for row in group}) > 1]
        chosen.update(occurrence_count=len(group), duplicate_count=len(group) - 1,
                      has_conflict=bool(conflicts), conflict_fields="|".join(conflicts))
        if "dico" in conflicts:
            chosen.update(dico=None, dicofre=None, locality_level="conflict", parish_match_method="conflict")
        elif "dicofre" in conflicts:
            chosen.update(dicofre=None, parish_match_method="conflict")
        rows.append(chosen)
    columns = BASE_COLUMNS + ["occurrence_count", "duplicate_count", "has_conflict", "conflict_fields"]
    return _typed(pd.DataFrame(rows, columns=columns))


def _coverage(listings, municipalities, manifest):
    rows = []
    for municipality in municipalities.itertuples(index=False):
        selected = listings[listings["dico"].eq(municipality.dico).fillna(False)]
        rows.append({"level": "municipio", "territory": municipality.dico, "name": municipality.official_name,
                     "listings": len(selected), "with_price": int(selected.asking_rent_eur.notna().sum()),
                     "with_parish": int(selected.dicofre.notna().sum())})
    regional = listings[listings["locality_level"] == "regiao"]
    for region, selected in regional.groupby("source_region"):
        rows.append({"level": "regiao", "territory": region, "name": region, "listings": len(selected),
                     "with_price": int(selected.asking_rent_eur.notna().sum()), "with_parish": 0})
    conflict = listings[listings["locality_level"] == "conflict"]
    if len(conflict):
        rows.append({"level": "conflict", "territory": "conflict", "name": "Conflitos territoriais",
                     "listings": len(conflict), "with_price": int(conflict.asking_rent_eur.notna().sum()),
                     "with_parish": 0})
    report = pd.DataFrame(rows)
    report["snapshot_month"] = manifest["snapshot_month"]
    report["source_run_id"] = manifest["run_id"]
    report["license_id"] = manifest["license_id"]
    report["attribution"] = manifest["attribution"]
    return report


def prepare_snapshot(root, output_dir, *, snapshot_month, processed_at_utc,
                     file_localities=None, parish_synonyms=None):
    """Verifica todo o lote antes de normalizar; só escreve na área candidata."""
    root, output_dir = Path(root), Path(output_dir)
    storage = LocalStorage(root)
    manifest = latest_snapshot(storage, snapshot_month)
    if manifest is None:
        raise IdealistaError(f"snapshot {snapshot_month} não importado; execute import_idealista_snapshot")
    silver = root / "lake" / "silver"
    for dimension in ("dim_municipality", "dim_parish"):
        if not (silver / dimension / "data.parquet").is_file():
            raise IdealistaError("dimensões CAOP ausentes; execute build_caop")
    municipalities = pd.read_parquet(silver / "dim_municipality" / "data.parquet")
    parishes = pd.read_parquet(silver / "dim_parish" / "data.parquet")
    resolver = TerritoryResolver(municipalities, parishes, file_localities=file_localities,
                                 parish_synonyms=parish_synonyms)
    inputs = []
    for entry in sorted(manifest["files"], key=lambda value: value["relative_path"]):
        path = storage.local_path(entry["key"])
        if not path.is_file():
            raise IdealistaError(f"raw ausente: {entry['key']}")
        digest = file_digest(path, key=entry["key"], region=entry["relative_path"])
        if digest["sha256"] != entry["sha256"] or digest["bytes"] != entry["bytes"]:
            raise IdealistaError(f"checksum/tamanho divergente: {entry['key']}")
        rows = read_rows(path)
        if len(rows) != entry["records"]:
            raise IdealistaError(f"contagem divergente: {entry['key']}")
        # Mesmo arquivos sem anúncios devem ter localidade conhecida.
        territory = resolver.resolve_file(entry["relative_path"])
        inputs.append((entry, rows, territory))
    records = []
    for entry, rows, territory in inputs:
        for index, row in enumerate(rows, 1):
            records.append({
                "listing_id": str(row["id"]).strip(), "source_id": "idealista", "snapshot_month": snapshot_month,
                **resolver.resolve_listing(territory, row.get("Titulo")), **normalize_listing(row),
                "source_run_id": manifest["run_id"], "raw_key": entry["key"], "raw_sha256": entry["sha256"],
                "relative_path": entry["relative_path"], "source_row": index, "collected_at_utc": None,
                "imported_at_utc": manifest["imported_at_utc"], "processed_at_utc": processed_at_utc,
                "license_id": manifest["license_id"], "attribution": manifest["attribution"],
            })
    occurrences = _typed(pd.DataFrame(records, columns=BASE_COLUMNS))
    listings = _unique(occurrences)
    coverage = _coverage(listings, municipalities, manifest)
    summary = {"snapshot_month": snapshot_month, "source_run_id": manifest["run_id"],
               "snapshot_sha256": manifest["snapshot_sha256"], "raw_bytes": sum(entry["bytes"] for entry in manifest["files"]),
               "imported_at_utc": manifest["imported_at_utc"], "collected_at_utc": None,
               "processed_at_utc": processed_at_utc, "files": len(inputs), "records": len(occurrences),
               "unique_listings": len(listings), "duplicate_occurrences": len(occurrences) - len(listings),
               "conflicting_listings": int(listings.has_conflict.sum()),
               "municipalities_expected": len(municipalities), "municipalities_with_listings": int(listings.dico.nunique()),
               "regional_listings": int(listings.locality_level.eq("regiao").sum()),
               "territorial_conflicts": int(listings.locality_level.eq("conflict").sum()),
               "listings_with_parish": int(listings.dicofre.notna().sum()),
               "municipal_listings_without_parish": int((listings.dico.notna() & listings.dicofre.isna()).sum()),
               "listings_with_quality_flags": int(listings.quality_flags.ne("").sum()),
               "missing_or_invalid_price": int(listings.asking_rent_eur.isna().sum()),
               "license_id": manifest["license_id"], "attribution": manifest["attribution"]}
    output_dir.mkdir(parents=True, exist_ok=True)
    occurrences.to_parquet(output_dir / "occurrences.parquet", engine="pyarrow", index=False)
    listings.to_parquet(output_dir / "listings.parquet", engine="pyarrow", index=False)
    coverage.to_csv(output_dir / "coverage.csv", sep=";", index=False, encoding="utf-8-sig")
    listings[listings.duplicate_count > 0].to_csv(output_dir / "duplicates.csv", sep=";", index=False, encoding="utf-8-sig")
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary
