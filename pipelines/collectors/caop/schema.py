"""Validação do ZIP/GeoPackage CAOP2025 antes do commit raw."""

import re
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import BadZipFile, ZipFile

import pyogrio

from pipelines.collectors._shared.catalog import REGIONS

EXPECTED_CRS = {
    "continente": {"EPSG:3763"},
    "acores": {"EPSG:5014", "EPSG:5015"},
    "madeira": {"EPSG:5016"},
}
REQUIRED_FIELDS = {
    "municipios": {"dtmn", "municipio", "distrito_ilha"},
    "freguesias": {"dtmnfr", "freguesia", "municipio", "distrito_ilha"},
}
MAX_UNCOMPRESSED_BYTES = 300 * 1024 * 1024
PARISH_CODE = re.compile(r"[0-9]{4}[0-9A-Z]{2}\Z")
MUNICIPALITY_CODE = re.compile(r"[0-9]{4}\Z")


class CaopSchemaError(ValueError):
    """O bruto não corresponde à estrutura CAOP esperada."""


def _validate_layer(path: Path, layer: str, kind: str, crs: str) -> set[str]:
    info = pyogrio.read_info(path, layer=layer)
    if info["crs"] != crs or info["geometry_type"] not in {"Polygon", "MultiPolygon"}:
        raise CaopSchemaError(f"{path.name}/{layer}: CRS ou geometria inesperada")
    missing = REQUIRED_FIELDS[kind] - set(info["fields"])
    if missing:
        raise CaopSchemaError(f"{path.name}/{layer}: campos ausentes: {', '.join(sorted(missing))}")
    if info["features"] < 1:
        raise CaopSchemaError(f"{path.name}/{layer}: camada vazia")
    code_field = "dtmn" if kind == "municipios" else "dtmnfr"
    name_field = "municipio" if kind == "municipios" else "freguesia"
    frame = pyogrio.read_dataframe(
        path, layer=layer, columns=[code_field, name_field], read_geometry=False
    )
    pattern = MUNICIPALITY_CODE if kind == "municipios" else PARISH_CODE
    if frame[code_field].isna().any() or frame[name_field].isna().any():
        raise CaopSchemaError(f"{path.name}/{layer}: código ou nome nulo")
    codes = set(frame[code_field].astype(str))
    if any(not pattern.fullmatch(code) for code in codes):
        raise CaopSchemaError(f"{path.name}/{layer}: código territorial inválido")
    return codes


def extract_gpkgs(archive: str | Path, region: str, directory: Path) -> list[Path]:
    """Extrai os GeoPackages do ZIP com os limites de segurança, para validar e transformar."""
    try:
        with ZipFile(archive) as zipped:
            members = [item for item in zipped.infolist() if item.filename.lower().endswith(".gpkg")]
            expected_count = 2 if region == "acores" else 1
            if len(members) != expected_count:
                raise CaopSchemaError(f"{region}: esperados {expected_count} GeoPackage(s)")
            if sum(item.file_size for item in members) > MAX_UNCOMPRESSED_BYTES:
                raise CaopSchemaError(f"{region}: ZIP excede o limite de inspeção")
            paths = []
            for member in members:
                if Path(member.filename).name != member.filename:
                    raise CaopSchemaError(f"{region}: caminho inseguro no ZIP")
                destination = directory / member.filename
                with zipped.open(member) as source, destination.open("wb") as target:
                    shutil.copyfileobj(source, target, length=1024 * 1024)
                paths.append(destination)
            return paths
    except BadZipFile as exc:
        raise CaopSchemaError(f"{region}: ZIP inválido") from exc


def select_layers(path: Path) -> dict[str, str]:
    """Encontra a única camada de municípios e a única de freguesias de um GeoPackage."""
    names = [name for name, _ in pyogrio.list_layers(path)]
    selected = {}
    for kind in ("municipios", "freguesias"):
        matching = [name for name in names if name.endswith(f"_{kind}")]
        if len(matching) != 1:
            raise CaopSchemaError(f"{path.name}: camada {kind} ausente ou ambígua")
        selected[kind] = matching[0]
    return selected


def validate_caop_archive(region: str, archive: str | Path) -> list[dict]:
    """Lê todas as bases do ZIP e confere camadas, campos, códigos e CRS."""
    if region not in REGIONS:
        raise CaopSchemaError(f"região desconhecida: {region}")
    with TemporaryDirectory(prefix="caop-schema-") as tmp:
        found_crs = set()
        results = []
        for path in extract_gpkgs(archive, region, Path(tmp)):
            selected = select_layers(path)
            crs = pyogrio.read_info(path, layer=selected["municipios"])["crs"]
            if crs not in EXPECTED_CRS[region] or crs in found_crs:
                raise CaopSchemaError(f"{path.name}: CRS inesperado ou repetido: {crs}")
            found_crs.add(crs)
            municipalities = _validate_layer(path, selected["municipios"], "municipios", crs)
            parishes = _validate_layer(path, selected["freguesias"], "freguesias", crs)
            if not {code[:4] for code in parishes}.issubset(municipalities):
                raise CaopSchemaError(f"{path.name}: freguesia sem município")
            results.append(
                {"member": path.name, "crs": crs, "layers": selected,
                 "municipalities": len(municipalities), "parishes": len(parishes)}
            )
        if found_crs != EXPECTED_CRS[region]:
            raise CaopSchemaError(f"{region}: grupos/CRS incompletos")
        return results
