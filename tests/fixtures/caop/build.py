"""Cria ZIPs CAOP mínimos para testes sem rede."""

import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

import geopandas as gpd
import pyogrio
from shapely.geometry import box

from pipelines.collectors._shared.catalog import get_source, load_catalog

GROUPS = {
    "continente": [("cont", "EPSG:3763", "0302", "0302FA")],
    "acores": [
        ("raa_oci", "EPSG:5014", "4801", "480101"),
        ("raa_cen_ori", "EPSG:5015", "4101", "410101"),
    ],
    "madeira": [("ram", "EPSG:5016", "3101", "310101")],
}


def make_archive(region: str, directory: str | Path, *, invalid_parish: bool = False) -> Path:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / f"{region}.gpkg.zip"
    with TemporaryDirectory(prefix="caop-fixture-") as tmp, ZipFile(
        archive, "w", compression=ZIP_DEFLATED
    ) as zipped:
        for prefix, crs, dico, dicofre in GROUPS[region]:
            path = Path(tmp) / f"{prefix}.gpkg"
            geometry = [box(0, 0, 1000, 1000)]
            municipality = gpd.GeoDataFrame(
                {"dtmn": [dico], "municipio": ["Município Sintético"], "distrito_ilha": ["Teste"]},
                geometry=geometry,
                crs=crs,
            )
            parish_code = "invalid" if invalid_parish else dicofre
            parish = gpd.GeoDataFrame(
                {
                    "dtmnfr": [parish_code],
                    "freguesia": ["Freguesia Sintética"],
                    "municipio": ["Município Sintético"],
                    "distrito_ilha": ["Teste"],
                },
                geometry=geometry,
                crs=crs,
            )
            pyogrio.write_dataframe(municipality, path, layer=f"{prefix}_municipios")
            pyogrio.write_dataframe(parish, path, layer=f"{prefix}_freguesias", append=True)
            zipped.write(path, arcname=path.name)
    return archive


def make_archives(directory: str | Path, **options) -> dict[str, Path]:
    return {region: make_archive(region, directory, **options) for region in GROUPS}


def offline_downloader(archives: dict[str, Path]):
    """Troca a rede por cópia dos ZIPs sintéticos, endereçados pelas URLs do catálogo."""
    urls = get_source(load_catalog())["urls"]
    by_url = {url: archives[region] for region, url in urls.items()}

    def download(url, destination):
        shutil.copyfile(by_url[url], destination)

    return download
