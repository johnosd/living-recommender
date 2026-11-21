"""Build completo do staging da mobilidade com dbt, sobre o fixture offline (spec 009, US1)."""
import hashlib

import pandas as pd
import pytest

from pipelines.cli import build_mobility as builder
from pipelines.collectors._shared.storage import LocalStorage
from tests.fixtures.mobility.ci_seed import seed
from tests.fixtures.mobility.responses import routes_ok

STAGING = "lake/bronze/stg_municipality_pole_distance/data.parquet"


def build(root, data):
    return builder.build_mobility(root, catalog=data["catalog"], poles_path=root / "poles.yml")


def content(root):
    frame = pd.read_parquet(root / STAGING).drop(columns=["processed_at_utc"])
    return hashlib.sha256(frame.sort_values(["dico", "pole_id", "mode"]).to_csv(index=False).encode()).hexdigest()


def test_straight_line_covers_every_pair_and_a_second_build_gives_the_same_content(tmp_path):
    data = seed(tmp_path)
    other = tmp_path / "lake/bronze/stg_observation/data.parquet"
    other.parent.mkdir(parents=True)
    other.write_bytes(b"previous observations")
    silver = tmp_path / "lake/silver/dim_municipality/data.parquet"
    before = silver.read_bytes()
    result = build(tmp_path, data)
    frame = pd.read_parquet(tmp_path / STAGING)
    line = frame[frame["mode"] == "straight_line"]
    assert len(line) == 5 * 4 and line["km"].notna().all() and (line["status"] == "ok").all()  # SC-001
    assert not frame.duplicated(["dico", "pole_id", "mode"]).any()  # SC-002
    assert set(frame["license_id"]) == {"CC-BY-4.0", "not_granted_by_source"}
    assert set(frame["dico"]) == set(pd.read_parquet(silver).dico)
    assert set(frame[frame["mode"] != "straight_line"]["status"]) == {"ok", "pendente"}  # identities are ok
    assert result["rows"] == len(frame) and silver.read_bytes() == before and other.read_bytes() == b"previous observations"
    first = content(tmp_path)
    build(tmp_path, data)
    assert content(tmp_path) == first
    assert (tmp_path / "lake/bronze/dim_mobility_pole/data.parquet").is_file()
    assert (tmp_path / "lake/bronze/mobility_coverage.csv").is_file()


def test_a_failed_build_keeps_the_previous_version(tmp_path, monkeypatch):
    data = seed(tmp_path)
    build(tmp_path, data)
    before = (tmp_path / STAGING).read_bytes()

    def boom(*args, **kwargs):
        raise builder.MobilityBuildError("dbt simulado falhou")

    monkeypatch.setattr(builder, "_run_dbt", boom)
    with pytest.raises(builder.MobilityBuildError, match="simulado"):
        build(tmp_path, data)
    assert (tmp_path / STAGING).read_bytes() == before
    assert not list((tmp_path / ".build/mobility").iterdir())  # the candidate directory is always removed


def test_a_state_for_an_unknown_municipality_fails_the_build(tmp_path):
    data = seed(tmp_path)
    storage = LocalStorage(tmp_path)
    item = "9999--aeroporto_x--driving"
    storage.put(f"raw/source=google_distances/dataset={item}/run_id=r/{item}.json", routes_ok().encode())
    from pipelines.collectors._shared.dataset_manifest import (
        encode_dataset_manifest,
        make_dataset_manifest,
    )
    from pipelines.collectors.mobility.catalog import mobility_source

    entry = {"dataset_id": item, "status": "changed", "key": f"raw/source=google_distances/dataset={item}/run_id=r/{item}.json",
             "sha256": "a" * 64, "bytes": 5, "fingerprint": "f"}
    manifest = make_dataset_manifest(mobility_source(data["catalog"]), source_id="google_distances", run_id="r",
                                     collected_at_utc="2026-11-21T10:00:00Z", datasets=[entry])
    storage.put("manifests/google_distances/r.json", encode_dataset_manifest(manifest))
    with pytest.raises(builder.MobilityBuildError, match="9999"):
        build(tmp_path, data)
    assert not (tmp_path / STAGING).exists()


def test_the_cli_reports_a_missing_silver_and_returns_one(tmp_path, capsys):
    assert builder.main(["--local", "--root", str(tmp_path)]) == 1
    assert "Silver" in capsys.readouterr().err
