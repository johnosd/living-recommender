"""Build completo local: raw -> Bronze -> Silver, sem rede."""

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from pipelines.cli import build_caop as builder
from pipelines.cli.view_caop import generate_view
from pipelines.collectors._shared.catalog import get_source, load_catalog
from pipelines.collectors._shared.manifest import encode_manifest, make_manifest
from pipelines.collectors._shared.storage import LocalStorage
from tests.fixtures.caop.ci_seed import RUN_ID, seed


def test_build_selects_changed_and_materializes_layers(tmp_path):
    root = tmp_path / "data"
    assert seed(root) == {"municipalities": 308, "parishes": 308}
    storage = LocalStorage(root)
    previous = json.loads(storage.get(f"manifests/caop/{RUN_ID}.json"))
    source = get_source(load_catalog(), strict_metadata=False)
    unchanged = make_manifest(
        source,
        run_id="later-unchanged",
        collected_at_utc="2026-11-05T00:00:00Z",
        status="unchanged",
        files=previous["files"],
        previous_changed_run_id=RUN_ID,
    )
    storage.put("manifests/caop/later-unchanged.json", encode_manifest(unchanged))

    result = builder.build_caop(root)
    assert result == {"run_id": RUN_ID, "version": "2025", "municipalities": 308, "parishes": 308}
    municipality = pd.read_parquet(root / "lake/silver/dim_municipality/data.parquet")
    parish = pd.read_parquet(root / "lake/silver/dim_parish/data.parquet")
    assert len(municipality) == 308
    assert len(parish) == 308
    assert {"0302FA", "0308FE"}.issubset(set(parish.dicofre))
    assert set(municipality.source_run_id) == {RUN_ID}
    assert set(parish.source_run_id) == {RUN_ID}
    assert (root / "lake/bronze/stg_caop_municipalities/data.parquet").is_file()
    assert (root / "lake/bronze/stg_caop_parishes/data.parquet").is_file()
    assert not (root / "lake/gold").exists()
    view = generate_view(root)
    html = view["html"].read_text(encoding="utf-8")
    assert "__CAOP_DATA__" not in html
    assert '"dicofre": "0302FA"' in html
    assert "0302FA" in view["parishes_csv"].read_text(encoding="utf-8-sig")
    assert len(pd.read_csv(view["municipalities_csv"], sep=";", dtype=str)) == 308


def test_build_failure_keeps_previous_silver(tmp_path, monkeypatch):
    root = tmp_path / "data"
    seed(root)
    builder.build_caop(root)
    silver = root / "lake/silver/dim_municipality/data.parquet"
    before = silver.read_bytes()

    def fail_dbt(_candidate: Path, _run_id: str) -> None:
        raise builder.BuildError("dbt falhou na fixture")

    monkeypatch.setattr(builder, "_run_dbt", fail_dbt)
    with pytest.raises(builder.BuildError, match="dbt falhou"):
        builder.build_caop(root)
    assert silver.read_bytes() == before


def test_spatial_check_rejects_point_outside(tmp_path):
    root = tmp_path / "data"
    seed(root)
    builder.build_caop(root)
    candidate = tmp_path / "candidate"
    shutil.copytree(root / "lake", candidate / "lake")
    path = candidate / "lake/silver/dim_parish/data.parquet"
    parish = pd.read_parquet(path)
    parish.loc[0, "representative_lat"] = 0.0
    parish.loc[0, "representative_lon"] = 0.0
    parish.to_parquet(path, index=False)
    with pytest.raises(builder.BuildError, match="ponto fora do território"):
        builder._validate_spatial(candidate, RUN_ID)


def test_build_rejects_changed_raw_checksum(tmp_path):
    root = tmp_path / "data"
    seed(root)
    storage = LocalStorage(root)
    manifest = json.loads(storage.get(f"manifests/caop/{RUN_ID}.json"))
    storage.local_path(manifest["files"][0]["key"]).write_bytes(b"alterado")
    with pytest.raises(builder.BuildError, match="checksum ou tamanho alterado"):
        builder.build_caop(root)
