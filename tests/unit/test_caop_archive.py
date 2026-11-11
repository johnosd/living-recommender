"""Extração e seleção de camadas compartilhadas pela validação e pela transformação."""

from zipfile import ZipFile

import pytest

from pipelines.collectors.caop.schema import (
    CaopSchemaError,
    extract_gpkgs,
    select_layers,
)
from tests.fixtures.caop.build import make_archive


def _zip_with(path, *names):
    with ZipFile(path, "w") as zipped:
        for name in names:
            zipped.writestr(name, b"conteudo")
    return path


def test_extract_gpkgs_returns_one_file_for_mainland_and_two_for_azores(tmp_path):
    for name in ("a", "b"):
        (tmp_path / name).mkdir()
    mainland = extract_gpkgs(make_archive("continente", tmp_path / "zips"), "continente", tmp_path / "a")
    azores = extract_gpkgs(make_archive("acores", tmp_path / "zips"), "acores", tmp_path / "b")
    assert [path.name for path in mainland] == ["cont.gpkg"]
    assert sorted(path.name for path in azores) == ["raa_cen_ori.gpkg", "raa_oci.gpkg"]


def test_select_layers_finds_municipality_and_parish_layers(tmp_path):
    path = extract_gpkgs(make_archive("madeira", tmp_path / "zips"), "madeira", tmp_path)[0]
    assert select_layers(path) == {"municipios": "ram_municipios", "freguesias": "ram_freguesias"}


def test_extract_gpkgs_rejects_wrong_count_unsafe_path_and_bad_zip(tmp_path):
    one = _zip_with(tmp_path / "one.zip", "so_um.gpkg")
    with pytest.raises(CaopSchemaError, match="esperados 2"):
        extract_gpkgs(one, "acores", tmp_path)
    unsafe = _zip_with(tmp_path / "unsafe.zip", "pasta/cont.gpkg")
    with pytest.raises(CaopSchemaError, match="inseguro"):
        extract_gpkgs(unsafe, "continente", tmp_path)
    broken = tmp_path / "broken.zip"
    broken.write_bytes(b"isto nao e um zip")
    with pytest.raises(CaopSchemaError, match="ZIP inválido"):
        extract_gpkgs(broken, "continente", tmp_path)
