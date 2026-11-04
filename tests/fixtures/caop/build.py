"""Cria ZIPs CAOP mínimos para testes sem rede."""

from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

import geopandas as gpd
import pyogrio
from shapely.geometry import box

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
