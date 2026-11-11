"""Geometria, nomes e códigos territoriais sem depender da DGT."""

import geopandas as gpd
import pytest
from pyproj import Transformer
from shapely.geometry import MultiPolygon, Point, box
from shapely.wkb import loads as load_wkb

from pipelines.collectors.caop.names import normalize_name
from pipelines.collectors.caop.transform import normalize_layer

PROVENANCE = {
    "source_run_id": "test-run",
    "caop_version": "2025",
    "reference_period": "2025",
    "license_id": "CC-BY-4.0",
    "collected_at_utc": "2026-11-04T00:00:00Z",
    "processed_at_utc": "2026-11-04T01:00:00Z",
}


@pytest.mark.parametrize(
    ("region", "crs"),
    [
        ("continente", "EPSG:3763"),
        ("acores", "EPSG:5014"),
        ("acores", "EPSG:5015"),
        ("madeira", "EPSG:5016"),
    ],
)
def test_multipart_area_and_representative_point_inside(region, crs):
    geometry = MultiPolygon([box(0, 0, 1000, 1000), box(3000, 0, 4000, 1000)])
    frame = gpd.GeoDataFrame(
        {"dtmn": ["0302"], "municipio": ["  Lagoa  do   AÇOR  "], "distrito_ilha": ["Teste"]},
        geometry=[geometry],
        crs=crs,
    )
    output = normalize_layer(frame, kind="municipios", region=region, provenance=PROVENANCE)
    row = output.iloc[0]
    lon, lat = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform(
        row.representative_lon, row.representative_lat
    )
    assert row.area_km2 == pytest.approx(2.0)
    assert load_wkb(row.geometry_wkb).covers(Point(lon, lat))
    assert row.official_name == "  Lagoa  do   AÇOR  "
    assert row.normalized_name == "lagoa do acor"


def test_parish_alphanumeric_code_and_homonymous_names_keep_identity():
    frame = gpd.GeoDataFrame(
        {
            "dtmnfr": ["0302FA", "0308FE"],
            "freguesia": ["São João", "São João"],
            "distrito_ilha": ["Braga", "Braga"],
        },
        geometry=[box(0, 0, 1000, 1000), box(2000, 0, 3000, 1000)],
        crs="EPSG:3763",
    )
    output = normalize_layer(frame, kind="freguesias", region="continente", provenance=PROVENANCE)
    assert set(output.dicofre) == {"0302FA", "0308FE"}
    assert set(output.dico) == {"0302", "0308"}
    assert set(output.normalized_name) == {"sao joao"}
    assert output.parish_type.isna().all()


def test_normalize_name_rejects_empty_and_collapses_spaces():
    assert normalize_name("  Évora\t  de   Cima ") == "evora de cima"
    with pytest.raises(ValueError, match="vazio"):
        normalize_name("   ")
