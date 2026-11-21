"""Preparação offline a partir de um único manifest completo e verificável."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from pipelines.cli._common import utc_now
from pipelines.collectors._shared.datasets import RUN_ID
from pipelines.collectors._shared.storage import LocalStorage, validate_key
from pipelines.collectors.censos2021.territory import align_censos
from pipelines.collectors.censos2021.transform import (
    canonical_code,
    harmonize_age_categories,
    read_censos_response,
)
from pipelines.collectors.censos2021.validate import (
    FAMILIES,
    age_categories,
    load_document,
    query_signature,
    validate_censos_catalog,
    validate_censos_response,
)

DEPENDENCIES = ("dim_parish", "dim_municipality", "xwalk_parish_2013_2025")


def sha256_file(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def raw_path(root, key):
    path = (Path(root) / validate_key(key)).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        raise ValueError("referência fora da raiz")
    return path


def dependency_hashes(root):
    return {
        table: sha256_file(Path(root) / "lake/silver" / table / "data.parquet")
        for table in DEPENDENCIES
    }


def selected_manifest(root, run_id=None):
    if run_id is not None and not RUN_ID.fullmatch(run_id):
        raise ValueError("run_id inválido")
    storage = LocalStorage(root)
    candidates = []
    for key in storage.list_keys():
        if key.startswith("manifests/censos/") and key.endswith(".json"):
            if run_id is not None and key != f"manifests/censos/{run_id}.json":
                continue
            doc = json.loads(storage.get(key))
            if doc.get("source_id") != "censos" or doc.get("schema_version") != 2:
                raise ValueError("manifest censitário inválido")
            if run_id is None or doc["run_id"] == run_id:
                candidates.append(
                    (
                        datetime.fromisoformat(doc["collected_at_utc"]),
                        doc["run_id"],
                        doc,
                    )
                )
    if not candidates:
        raise ValueError("manifest censitário não encontrado")
    doc = max(candidates, key=lambda x: x[:2])[2]
    if doc["status"] not in ("changed", "unchanged") or any(
        e["status"] not in ("changed", "unchanged") for e in doc["datasets"]
    ):
        raise ValueError("run censitário mais recente/selecionado incompleto")
    if not doc["datasets"] or len({e["dataset_id"] for e in doc["datasets"]}) != len(
        doc["datasets"]
    ):
        raise ValueError("manifest vazio/duplicado")
    return doc


def prepare_censos(root: Path, candidate: Path, *, run_id=None, catalog_path=None):
    """Retorna resumo e grava quatro entradas Parquet; nunca consulta a rede nem promove."""
    root, candidate = Path(root).resolve(), Path(candidate).resolve()
    hashes = dependency_hashes(root)
    dim = pd.read_parquet(root / "lake/silver/dim_parish/data.parquet")
    municipalities = pd.read_parquet(root / "lake/silver/dim_municipality/data.parquet")
    crosswalk = pd.read_parquet(
        root / "lake/silver/xwalk_parish_2013_2025/data.parquet"
    )
    if not dim.dico.isin(municipalities.dico).all() or dim.dicofre.duplicated().any():
        raise ValueError("dimensão municipal/freguesia inválida")
    if set(dim.caop_version.astype(str)) != {"2025"}:
        raise ValueError("geografia CAOP não suportada; requer nova comprovação")
    manifest = selected_manifest(root, run_id)
    entries = {e["dataset_id"]: e for e in manifest["datasets"]}
    docs = {}
    snapshots = {}
    for dataset_id, entry in entries.items():
        snap = entry.get("dataset_snapshot")
        if (
            not snap
            or snap.get("id") != dataset_id
            or entry.get("query_signature") != query_signature(snap)
        ):
            raise ValueError("snapshot/assinatura de consulta ausente ou incompatível")
        path = raw_path(root, entry["key"])
        if not entry["key"].startswith(f"raw/source=censos/dataset={dataset_id}/"):
            raise ValueError("referência raw de outra fonte/dataset")
        if sha256_file(path) != entry["sha256"]:
            raise ValueError(f"hash inválido: {dataset_id}")
        validate_censos_response(snap, path)
        docs[dataset_id] = load_document(path)
        snapshots[dataset_id] = snap
    validate_censos_catalog(
        {
            "sources": {
                "censos": {
                    "license_id": manifest["license_id"],
                    "collection_method": "api_json",
                    "datasets": list(snapshots.values()),
                }
            }
        }
    )
    if catalog_path is not None:
        from pipelines.collectors._shared.catalog import load_catalog

        if {
            d["id"]
            for d in validate_censos_catalog(load_catalog(catalog_path))["datasets"]
        } != set(entries):
            raise ValueError("seleção de catálogo diverge do snapshot")
    metadata_entries = {k: d for k, d in snapshots.items() if d["role"] == "metadata"}
    if {d["indicator"] for d in metadata_entries.values()} != set(FAMILIES):
        raise ValueError("família de metadados obrigatória ausente")
    native_categories = []
    originals = []
    now = utc_now()
    for meta_id, meta_snap in metadata_entries.items():
        meta = docs[meta_id]
        indicator = meta_snap["indicator"]
        geo, expected_ages = FAMILIES[indicator]
        cats = age_categories(meta)
        if set(cats.age_code) != set(expected_ages):
            raise ValueError(
                "conjunto etário obrigatório diferente do verificado; revisar a seleção"
            )
        descriptions = meta["Dimensoes"]["Descricao_Dim"]
        version = next((d["versao"] for d in descriptions if d["dim_num"] == "2"), None)
        expected_version = "05723" if geo == "2025" else "04479"
        if version != expected_version or not meta_snap.get("geography_evidence"):
            raise ValueError("evidência territorial/geografia oficial insuficiente")
        geo_items = [
            x
            for g in meta["Dimensoes"]["Categoria_Dim"]
            for a in g.values()
            for x in a
            if x.get("dim_num") == "2" and str(x.get("categ_nivel")) == "6"
        ]
        declared = {x["categ_cod"] for x in geo_items}
        if not declared:
            raise ValueError("universo de freguesias ausente dos metadados")
        if geo == "2025" and declared != set(dim.dicofre):
            raise ValueError("universo territorial oficial difere da CAOP vigente")
        selected = [
            d
            for d in snapshots.values()
            if d["role"] == "data" and d["metadata_dataset_id"] == meta_id
        ]
        releases = {entries[d["id"]].get("source_release_date") for d in selected}
        if len(releases) != 1 or None in releases:
            raise ValueError(
                "revisões oficiais incompatíveis ou não verificadas na mesma família"
            )
        cats = cats.assign(
            indicator=indicator,
            geography_version=geo,
            metadata_dataset_id=meta_id,
            raw_key=entries[meta_id]["key"],
            raw_sha256=entries[meta_id]["sha256"],
            license_id=manifest["license_id"],
            attribution=manifest.get("attribution", "INE"),
            source_run_id=manifest["run_id"],
            collected_at_utc=manifest["collected_at_utc"],
            processed_at_utc=now,
        )
        native_categories.append(cats)
        family_keys = set()
        for dataset in selected:
            entry = entries[dataset["id"]]
            frame = read_censos_response(dataset, raw_path(root, entry["key"]), meta)
            keys = set(zip(frame.source_dicofre, frame.age_code, strict=True))
            if family_keys & keys:
                raise ValueError("registro de origem duplicado entre lotes/consultas")
            family_keys.update(keys)
            if not frame.source_dicofre.str[:4].isin(municipalities.dico).all():
                raise ValueError("município de origem sem correspondência")
            frame = frame.assign(
                raw_key=entry["key"],
                raw_sha256=entry["sha256"],
                source_run_id=entry.get("previous_changed_run_id")
                or manifest["run_id"],
                metadata_raw_key=entries[meta_id]["key"],
                metadata_raw_sha256=entries[meta_id]["sha256"],
                query_signature=entry["query_signature"],
                collected_at_utc=manifest["collected_at_utc"],
                processed_at_utc=now,
                license_id=manifest["license_id"],
                attribution=manifest.get("attribution", "INE"),
                source_release_date=entry.get("source_release_date"),
                geography_evidence=dataset["geography_evidence"],
                reexpression_method=dataset.get(
                    "reexpression_method", "not_disclosed_by_publisher"
                ),
            )
            originals.append(frame)
        if family_keys != {(code, age) for code in declared for age in cats.age_code}:
            raise ValueError("registro de origem perdido/extra na união dos lotes")
    observations = pd.concat(originals, ignore_index=True)
    for _, group in observations.groupby(["indicator", "source_dicofre", "period"]):
        total = group.loc[group.is_total & group.value_status.eq("observed"), "value"]
        known = group.loc[~group.is_total & group.value_status.eq("observed"), "value"]
        if len(total) == 1 and int(known.sum()) > int(total.iloc[0]):
            raise ValueError("coerência etária: soma conhecida excede total oficial")
        if group.value_status.eq("observed").all():
            total = group.loc[group.is_total, "value"]
            ages = group.loc[~group.is_total, "value"]
            if len(total) != 1 or int(total.iloc[0]) != int(ages.sum()):
                raise ValueError("coerência etária com total oficial reprovada")
    canonical = harmonize_age_categories(observations, None)
    primary = pd.concat(native_categories).query("geography_version == '2025'").copy()
    primary["age_code"] = primary.apply(canonical_code, axis=1)
    primary = primary[
        ["age_code", "age_min", "age_max", "is_total", "is_unknown"]
    ].drop_duplicates()
    if not {
        "25_29",
        "30_34",
        "35_39",
        "65_69",
        "70_74",
        "75_79",
        "80_84",
        "85_plus",
    } <= set(primary.age_code):
        raise ValueError("faixas necessárias não verificadas")
    prepared = align_censos(
        canonical, dim, crosswalk, categories=primary, target_version="2025"
    )
    prepared["period"] = "2021"
    for table, digest in hashes.items():
        prepared[f"{table}_sha256"] = digest
    orphan_rows = prepared.attrs.pop("orphans", [])
    candidate.mkdir(parents=True, exist_ok=True)
    output = candidate / "prepared"
    output.mkdir(exist_ok=True)
    for filename, frame in [
        ("census_age_category", pd.concat(native_categories, ignore_index=True)),
        ("census_observation", observations),
        ("census_parish_observation", prepared),
    ]:
        frame.to_parquet(output / f"{filename}.parquet", index=False)
        layer = (
            "bronze"
            if filename in ("census_age_category", "census_observation")
            else "silver"
        )
        (candidate / "lake" / layer / filename).mkdir(parents=True, exist_ok=True)
    return {
        "period": "2021",
        "run_id": manifest["run_id"],
        "parishes": len(dim),
        "observations": len(prepared),
        "dependency_hashes": hashes,
        "orphans": orphan_rows,
        "prepared": prepared,
        "parishes_frame": dim,
        "categories": primary,
    }
