"""Prepara a CAOP geográfica para os modelos Bronze e Silver do dbt."""

from pathlib import Path
from tempfile import TemporaryDirectory

import geopandas as gpd
import pandas as pd
import pyogrio

from pipelines.collectors._shared.catalog import REGIONS
from pipelines.collectors.caop.names import normalize_name
from pipelines.collectors.caop.schema import (
    EXPECTED_CRS,
    MUNICIPALITY_CODE,
    PARISH_CODE,
    CaopSchemaError,
    extract_gpkgs,
    select_layers,
)

REGION_NAMES = {
    "continente": None,
    "acores": "Região Autónoma dos Açores",
    "madeira": "Região Autónoma da Madeira",
}


def normalize_layer(
    frame: gpd.GeoDataFrame, *, kind: str, region: str, provenance: dict
) -> pd.DataFrame:
    """Dissolve partes com o mesmo código e calcula área e ponto interno."""
    if kind not in {"municipios", "freguesias"} or region not in REGION_NAMES:
        raise ValueError("camada ou região desconhecida")
    code_field = "dtmn" if kind == "municipios" else "dtmnfr"
    name_field = "municipio" if kind == "municipios" else "freguesia"
    pattern = MUNICIPALITY_CODE if kind == "municipios" else PARISH_CODE
    required = {code_field, name_field, "distrito_ilha"}
    if not required.issubset(frame.columns) or frame.empty or frame.crs is None:
        raise CaopSchemaError(f"{region}/{kind}: campos, linhas ou CRS ausentes")
    crs = frame.crs.to_string()
    if crs not in EXPECTED_CRS[region]:
        raise CaopSchemaError(f"{region}/{kind}: CRS inesperado: {crs}")
    if frame[list(required)].isna().any().any():
        raise CaopSchemaError(f"{region}/{kind}: código, nome ou distrito/ilha nulo")
    codes = frame[code_field].astype(str)
    if any(pattern.fullmatch(code) is None for code in codes):
        raise CaopSchemaError(f"{region}/{kind}: código territorial inválido")
    if frame.geometry.isna().any() or frame.geometry.is_empty.any() or (~frame.geometry.is_valid).any():
        raise CaopSchemaError(f"{region}/{kind}: geometria ausente ou inválida")
    for _, group in frame.groupby(code_field, sort=False):
        if group[name_field].nunique() != 1 or group["distrito_ilha"].nunique() != 1:
            raise CaopSchemaError(f"{region}/{kind}: partes do mesmo código divergem")

    dissolved = frame.dissolve(by=code_field, as_index=False, aggfunc="first", sort=False)
    areas = dissolved.geometry.area / 1_000_000
    points = dissolved.geometry.representative_point()
    if (areas <= 0).any() or not dissolved.geometry.covers(points).all():
        raise CaopSchemaError(f"{region}/{kind}: área ou ponto inválido")
    wgs84_points = gpd.GeoSeries(points, crs=frame.crs).to_crs("EPSG:4326")
    rows = []
    for idx, row in dissolved.iterrows():
        code = str(row[code_field])
        result = {
            "official_name": str(row[name_field]),
            "normalized_name": normalize_name(str(row[name_field])),
            "district_or_island": str(row["distrito_ilha"]),
            "autonomous_region": REGION_NAMES[region],
            "region": region,
            "source_crs": crs,
            "geometry_wkb": row.geometry.wkb,
            "area_km2": float(areas.loc[idx]),
            "representative_lat": float(wgs84_points.loc[idx].y),
            "representative_lon": float(wgs84_points.loc[idx].x),
            **provenance,
        }
        if kind == "municipios":
            result["dico"] = code
        else:
            result["dicofre"] = code
            result["dico"] = code[:4]
            result["parish_type"] = (
                str(row["parish_type"]) if "parish_type" in row and pd.notna(row["parish_type"])
                else None
            )
        rows.append(result)
    return pd.DataFrame(rows)


def prepare_caop(
    archives: dict[str, Path], manifest: dict, output_dir: Path, *, processed_at_utc: str
) -> dict[str, int]:
    """Lê os três brutos e escreve dois Parquets intermediários selecionados."""
    if set(archives) != set(REGIONS) or manifest.get("status") != "changed":
        raise CaopSchemaError("coleta completa changed das três regiões é obrigatória")
    provenance = {
        "source_run_id": manifest["run_id"],
        "caop_version": str(manifest["version"]),
        "reference_period": str(manifest["reference_period"]),
        "license_id": manifest["license_id"],
        "collected_at_utc": manifest["collected_at_utc"],
        "processed_at_utc": processed_at_utc,
    }
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    all_rows: dict[str, list[pd.DataFrame]] = {"municipios": [], "freguesias": []}
    with TemporaryDirectory(prefix="caop-transform-", dir=output_dir) as tmp:
        for region in REGIONS:
            for path in extract_gpkgs(archives[region], region, Path(tmp)):
                layers = select_layers(path)
                for kind, bucket in all_rows.items():
                    frame = pyogrio.read_dataframe(path, layer=layers[kind])
                    bucket.append(
                        normalize_layer(frame, kind=kind, region=region, provenance=provenance)
                    )
                path.unlink()
    municipalities = pd.concat(all_rows["municipios"], ignore_index=True)
    parishes = pd.concat(all_rows["freguesias"], ignore_index=True)
    if municipalities["dico"].duplicated().any() or parishes["dicofre"].duplicated().any():
        raise CaopSchemaError("códigos territoriais repetidos entre regiões")
    if not set(parishes["dico"]).issubset(set(municipalities["dico"])):
        raise CaopSchemaError("freguesia sem município correspondente")
    municipalities.to_parquet(output_dir / "municipalities.parquet", index=False)
    parishes.to_parquet(output_dir / "parishes.parquet", index=False)
    return {"municipalities": len(municipalities), "parishes": len(parishes)}
