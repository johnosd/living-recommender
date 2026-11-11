"""Gera uma CAOP sintética nacional, sem rede, para dbt e testes de integração."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

import geopandas as gpd
import pyogrio
from shapely.geometry import MultiPolygon, box

from pipelines.collectors._shared.catalog import get_source, load_catalog
from pipelines.collectors._shared.manifest import (
    encode_manifest,
    file_digest,
    make_manifest,
    validate_changed,
)
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors.caop.transform import prepare_caop

RUN_ID = "ci-fixture"
COLLECTED_AT = "2026-11-04T00:00:00Z"
PROCESSED_AT = "2026-11-04T01:00:00Z"


def _groups() -> dict[str, list[tuple[str, str, list[str]]]]:
    mainland = [f"{number:04d}" for number in range(1, 277)] + ["0302", "0308"]
    return {
        "continente": [("cont", "EPSG:3763", mainland)],
        "acores": [
            ("raa_oci", "EPSG:5014", [f"480{number}" for number in range(1, 4)]),
            ("raa_cen_ori", "EPSG:5015", [f"{number:04d}" for number in range(4101, 4117)]),
        ],
        "madeira": [("ram", "EPSG:5016", [f"{number:04d}" for number in range(3101, 3112)])],
    }


def _archive(region: str, groups: list[tuple[str, str, list[str]]], destination: Path) -> None:
    with TemporaryDirectory(prefix="caop-seed-") as tmp, ZipFile(
        destination, "w", compression=ZIP_DEFLATED
    ) as zipped:
        for prefix, crs, codes in groups:
            path = Path(tmp) / f"{prefix}.gpkg"
            geometries = []
            for index in range(len(codes)):
                x = index * 3000
                parts = [box(x, 0, x + 1000, 1000)]
                if index == 0:
                    parts.append(box(x + 1500, 0, x + 1800, 300))
                geometries.append(MultiPolygon(parts))
            names = ["Lagoa" if index == 0 else f"Município {code}" for index, code in enumerate(codes)]
            municipality = gpd.GeoDataFrame(
                {
                    "dtmn": codes,
                    "municipio": names,
                    "distrito_ilha": [region] * len(codes),
                },
                geometry=geometries,
                crs=crs,
            )
            parish_codes = [
                "0302FA" if code == "0302" else "0308FE" if code == "0308" else f"{code}01"
                for code in codes
            ]
            parish = gpd.GeoDataFrame(
                {
                    "dtmnfr": parish_codes,
                    "freguesia": [f"Freguesia {code}" for code in parish_codes],
                    "municipio": names,
                    "distrito_ilha": [region] * len(codes),
                },
                geometry=geometries,
                crs=crs,
            )
            pyogrio.write_dataframe(municipality, path, layer=f"{prefix}_municipios")
            pyogrio.write_dataframe(parish, path, layer=f"{prefix}_freguesias", append=True)
            zipped.write(path, arcname=path.name)


def seed(root: Path) -> dict[str, int]:
    """Escreve raw/manifest changed e o Parquet preparado para dbt."""
    root = Path(root)
    storage = LocalStorage(root)
    manifest_key = f"manifests/caop/{RUN_ID}.json"
    if manifest_key in storage.list_keys():
        manifest = json.loads(storage.get(manifest_key))
        validate_changed(manifest)
        archives = {}
        for entry in manifest["files"]:
            archive = storage.local_path(entry["key"])
            if not archive.is_file() or file_digest(
                archive, key=entry["key"], region=entry["region"]
            )["sha256"] != entry["sha256"]:
                raise ValueError("fixture raw existente não corresponde ao manifest")
            archives[entry["region"]] = archive
    else:
        source = get_source(load_catalog(), strict_metadata=False)
        archives = {}
        entries = []
        with TemporaryDirectory(prefix="caop-seed-archives-") as tmp:
            for region, groups in _groups().items():
                archive = Path(tmp) / f"{region}.gpkg.zip"
                _archive(region, groups, archive)
                key = f"raw/source=caop/version={source['version']}/run_id={RUN_ID}/{archive.name}"
                storage.put_file(key, archive)
                archives[region] = storage.local_path(key)
                entries.append(file_digest(archive, key=key, region=region))
        manifest = make_manifest(
            source, run_id=RUN_ID, collected_at_utc=COLLECTED_AT, status="changed", files=entries
        )
        storage.put(manifest_key, encode_manifest(manifest))
    counts = prepare_caop(archives, manifest, root / "prepared", processed_at_utc=PROCESSED_AT)
    for name in ("stg_caop_municipalities", "stg_caop_parishes"):
        (root / "lake" / "bronze" / name).mkdir(parents=True, exist_ok=True)
    for name in ("dim_municipality", "dim_parish"):
        (root / "lake" / "silver" / name).mkdir(parents=True, exist_ok=True)
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera fixture CAOP nacional para dbt.")
    parser.add_argument("--root", type=Path, default=Path(".data/ci"))
    arguments = parser.parse_args()
    print(seed(arguments.root))
