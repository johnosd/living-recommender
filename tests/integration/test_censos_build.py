"""Pipeline censitário offline com dependências pequenas e reais arquivos Parquet."""

import hashlib
import json
import shutil

import pandas as pd
import pytest

from pipelines.cli.build_censos import TABLES, build_censos
from pipelines.collectors.censos2021.prepare import prepare_censos
from tests.fixtures.censos2021.ci_seed import seed


@pytest.mark.parametrize("case", ["lost_batch", "overlapping_batches"])
def test_national_union_rejects_missing_or_overlapping_batches(tmp_path, case):
    root = tmp_path / "root"
    seed(root)
    p = root / "manifests/censos/fixture.json"
    manifest = json.loads(p.read_text("utf8"))
    entries = [
        e for e in manifest["datasets"] if e["dataset_snapshot"].get("age_codes")
    ]
    if case == "lost_batch":
        manifest["datasets"].remove(entries[0])
    else:
        # Two individually valid responses with identical geographic/age keys.
        from copy import deepcopy

        from pipelines.collectors.censos2021.validate import query_signature

        duplicate = deepcopy(entries[0])
        duplicate["dataset_id"] += "_duplicate"
        duplicate["dataset_snapshot"]["id"] = duplicate["dataset_id"]
        duplicate["query_signature"] = query_signature(duplicate["dataset_snapshot"])
        raw = root / duplicate["key"]
        duplicate["key"] = duplicate["key"].replace(
            entries[0]["dataset_id"], duplicate["dataset_id"]
        )
        target = root / duplicate["key"]
        target.parent.mkdir(parents=True)
        target.write_bytes(raw.read_bytes())
        manifest["datasets"].append(duplicate)
    p.write_text(json.dumps(manifest), encoding="utf8")
    with pytest.raises(ValueError, match="perdido|duplicado"):
        prepare_censos(root, tmp_path / "bad")


def test_historical_single_age_manifest_remains_rebuildable(tmp_path, monkeypatch):
    from copy import deepcopy

    from pipelines.collectors.censos2021.coverage import assess_censos_coverage
    from tests.fixtures.censos2021 import ci_seed

    old = ci_seed.fixture_catalog()
    source = old["sources"]["censos"]
    historical = [d for d in source["datasets"] if d["role"] == "metadata"]
    for geo in ("2025", "2013"):
        template = next(
            d
            for d in source["datasets"]
            if d["role"] == "data" and d["geography_version"] == geo
        )
        for age in template["age_codes"]:
            d = deepcopy(template)
            d.pop("age_codes")
            d.pop("parish_codes")
            d.update(id=f"pop_{geo}_{age}", age_code=age)
            d["params"].update(Dim2="lvl@6", Dim4=age)
            historical.append(d)
    source["datasets"] = historical
    monkeypatch.setattr(ci_seed, "fixture_catalog", lambda: old)
    root = tmp_path / "root"
    result = seed(root)
    assert result["status"] == "changed" and len(result["datasets"]) == 41
    summary = prepare_censos(root, tmp_path / "candidate")
    assert summary["observations"] == 114
    assert assess_censos_coverage(
        summary["prepared"], summary["parishes_frame"], summary["categories"]
    )["ready"]


def simulated_dbt(candidate, silver):
    for table, layer in TABLES.items():
        path = candidate / f"lake/{layer}/{table}/data.parquet"
        shutil.copyfile(candidate / f"prepared/{table}.parquet", path)


def snapshot(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (root / "lake").rglob("*")
        if p.is_file()
    }


def test_prepare_is_offline_and_detects_corrupt_raw_or_latest_failed_run(tmp_path):
    root = tmp_path / "root"
    seed(root)
    summary = prepare_censos(root, tmp_path / "candidate")
    assert (
        summary["observations"]
        == len(pd.read_parquet(root / "lake/silver/dim_parish/data.parquet")) * 19
    )
    manifests = sorted((root / "manifests/censos").glob("*.json"))
    doc = json.loads(manifests[0].read_text("utf8"))
    raw = root / doc["datasets"][0]["key"]
    raw.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="hash"):
        prepare_censos(root, tmp_path / "bad")


def test_partial_manifest_blocks_default_but_explicit_previous_run_is_allowed(tmp_path):
    root = tmp_path / "root"
    seed(root)
    first = next((root / "manifests/censos").glob("*.json"))
    original = json.loads(first.read_text("utf8"))
    bad = {
        **original,
        "run_id": "failed",
        "collected_at_utc": "2026-11-14T00:00:00Z",
        "status": "partial",
    }
    (first.parent / "failed.json").write_text(json.dumps(bad), encoding="utf8")
    with pytest.raises(ValueError, match="incompleto"):
        prepare_censos(root, tmp_path / "bad")
    assert (
        prepare_censos(root, tmp_path / "ok", run_id=original["run_id"])["period"]
        == "2021"
    )


def test_native_reconciliation_refuses_missing_rows_and_wrong_totals(tmp_path):
    root = tmp_path / "root"
    seed(root)
    p = next((root / "manifests/censos").glob("*.json"))
    doc = json.loads(p.read_text("utf8"))
    entry = next(
        e
        for e in doc["datasets"]
        if e["dataset_snapshot"].get("age_codes")
        and e["dataset_snapshot"]["geography_version"] == "2025"
    )
    path = root / entry["key"]
    data = json.loads(path.read_text("utf8"))
    next(r for r in data[0]["Dados"]["2021"] if r["dim_4"] == "32")["valor"] = "999"
    content = json.dumps(data).encode()
    path.write_bytes(content)
    entry["sha256"] = hashlib.sha256(content).hexdigest()
    p.write_text(json.dumps(doc), encoding="utf8")
    with pytest.raises(ValueError, match="coerência"):
        prepare_censos(root, tmp_path / "bad")


def test_dbt_real_build_and_reports(tmp_path):
    root = tmp_path / "root"
    seed(root)
    result = build_censos(root)
    assert result["ready"] and result["counts"] == {
        "own": 76,
        "inherited": 19,
        "missing": 19,
    }
    summary = pd.read_csv(root / "lake/silver/census_reports/summary.csv")
    assert {"country", "region", "municipality"} == set(summary.scope)
    assert "value" not in summary.columns


@pytest.mark.parametrize(
    "case", ["dbt", "missing_output", "report", "dependency", "rename"]
)
def test_failures_preserve_all_previous_tables(tmp_path, monkeypatch, case):
    from pipelines.cli import _promote
    from pipelines.cli import build_censos as module

    root = tmp_path / "root"
    seed(root)
    build_censos(root, dbt_runner=simulated_dbt)
    before = snapshot(root)

    def failing_runner(candidate, silver):
        if case == "dbt":
            raise ValueError("dbt failed")
        simulated_dbt(candidate, silver)
        if case == "missing_output":
            (candidate / "lake/silver/census_coverage/data.parquet").unlink()
        if case == "dependency":
            # Simulate dependency race via the digest collaborator, without corrupting territorial data.
            monkeypatch.setattr(
                module, "dependency_hashes", lambda root: {"changed": "yes"}
            )

    if case == "report":
        monkeypatch.setattr(
            module,
            "write_censos_reports",
            lambda *args: (_ for _ in ()).throw(OSError("report failed")),
        )
    if case == "rename":
        original = _promote.os.replace

        def fail_once(source, dest):
            if Path(source).name == "census_coverage" and ".build" in str(source):
                raise OSError("rename failed")
            return original(source, dest)

        from pathlib import Path

        monkeypatch.setattr(_promote.os, "replace", fail_once)
    with pytest.raises((ValueError, OSError, AssertionError)):
        build_censos(root, dbt_runner=failing_runner)
    assert snapshot(root) == before
    assert list((root / "reports/censos").rglob("failure.json"))


def test_lock_is_exclusive_and_stale_lock_requires_explicit_recovery(tmp_path):
    root = tmp_path / "root"
    seed(root)
    lock = root / ".build/censos/build.lock"
    lock.parent.mkdir(parents=True)
    lock.write_text("interrupted", encoding="utf8")
    with pytest.raises(ValueError, match="ocupado/interrompido"):
        build_censos(root, dbt_runner=simulated_dbt)
    assert lock.read_text("utf8") == "interrupted"


def test_overlapping_build_is_refused_without_removing_active_lock(tmp_path):
    root = tmp_path / "root"
    seed(root)

    def runner(candidate, silver):
        with pytest.raises(ValueError, match="ocupado"):
            build_censos(root, dbt_runner=simulated_dbt)
        assert (root / ".build/censos/build.lock").is_file()
        simulated_dbt(candidate, silver)

    assert build_censos(root, dbt_runner=runner)["ready"]


def test_partial_known_age_sum_cannot_exceed_total_when_other_age_is_suppressed(
    tmp_path,
):
    root = tmp_path / "root"
    seed(root)
    p = next((root / "manifests/censos").glob("*.json"))
    manifest = json.loads(p.read_text("utf8"))
    for entry in manifest["datasets"]:
        snap = entry["dataset_snapshot"]
        if snap.get("geography_version") != "2025" or snap["role"] != "data":
            continue
        path = root / entry["key"]
        data = json.loads(path.read_text("utf8"))
        for row in data[0]["Dados"]["2021"]:
            if row["geocod"] != "010103":
                continue
            if row["dim_4"] == "32":
                row["valor"] = "999"
            elif row["dim_4"] == "41":
                row.pop("valor")
                row.update(
                    sinal_conv="x", sinal_conv_desc="Dado confidencial", ind_string="x"
                )
        content = json.dumps(data).encode()
        path.write_bytes(content)
        entry["sha256"] = hashlib.sha256(content).hexdigest()
    p.write_text(json.dumps(manifest), encoding="utf8")
    with pytest.raises(ValueError, match="coerência"):
        prepare_censos(root, tmp_path / "bad")


def test_outputs_resolving_outside_root_are_rejected_before_any_write(tmp_path):
    from pipelines.cli.build_censos import verify_destination_paths

    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    # pathlib resolution covers symlinks and Windows junctions without deleting their target.
    from pathlib import Path
    from unittest.mock import patch

    original = Path.resolve

    def redirected(path, *args, **kwargs):
        if path == root / "lake/silver/census_reports":
            return outside
        return original(path, *args, **kwargs)

    with (
        patch.object(Path, "resolve", redirected),
        pytest.raises(ValueError, match="fora da raiz"),
    ):
        verify_destination_paths(root)
    assert not list(outside.iterdir())


def test_explicit_run_is_independent_of_unrelated_invalid_manifests(tmp_path):
    root = tmp_path / "root"
    seed(root)
    (root / "manifests/censos/unrelated.json").write_text("not JSON", encoding="utf8")
    assert prepare_censos(root, tmp_path / "ok", run_id="fixture")["period"] == "2021"


def test_build_rejects_different_release_dates_inside_same_family(tmp_path):
    root = tmp_path / "root"
    seed(root)
    p = root / "manifests/censos/fixture.json"
    manifest = json.loads(p.read_text("utf8"))
    next(e for e in manifest["datasets"] if e["dataset_snapshot"].get("age_codes"))[
        "source_release_date"
    ] = "1900-01-01"
    p.write_text(json.dumps(manifest), encoding="utf8")
    with pytest.raises(ValueError, match="revisões"):
        prepare_censos(root, tmp_path / "bad")


def test_post_commit_backup_cleanup_failure_is_maintenance_warning_not_failed_build(
    tmp_path, monkeypatch
):
    from pathlib import Path

    from pipelines.cli import _promote

    root = tmp_path / "root"
    seed(root)
    build_censos(root, dbt_runner=simulated_dbt)
    before = snapshot(root)
    original = _promote.shutil.rmtree

    def deny_backup(path, *args, **kwargs):
        if Path(path).name.startswith(".previous-"):
            raise OSError("backup cleanup denied")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(_promote.shutil, "rmtree", deny_backup)

    def changed_runner(candidate, silver):
        path = candidate / "prepared/census_observation.parquet"
        frame = pd.read_parquet(path).assign(processed_at_utc="2099-01-01T00:00:00Z")
        frame.to_parquet(path, index=False)
        simulated_dbt(candidate, silver)

    result = build_censos(root, dbt_runner=changed_runner)
    assert result["ready"] and result["maintenance_warnings"]
    assert snapshot(root) != before
