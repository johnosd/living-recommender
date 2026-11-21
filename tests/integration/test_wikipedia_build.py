"""Cenários controlados de entrada/exports/promoção; dbt real no quickstart/CI."""

import shutil
from pathlib import Path

import pytest

from pipelines.cli.build_wikipedia import build, verify_current
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors.wikipedia.handler import collect_wikipedia
from pipelines.collectors.wikipedia.local import source_lock
from pipelines.collectors.wikipedia.manifest import encode
from pipelines.collectors.wikipedia.prepare import SCHEMAS, TABLES
from pipelines.collectors.wikipedia.promotion import (
    PROMOTED,
    output_hashes,
    promote,
    recover,
)
from tests.fixtures.wikipedia.ci_seed import seed
from tests.fixtures.wikipedia.responses import (
    associations,
    catalog,
    fetcher,
    municipalities,
)


def controlled_exports(candidate, silver):
    """Colaborador dbt controlado: exports reais, resultados explicitamente sintéticos."""
    for table, layer in TABLES.items():
        destination = candidate / f"lake/{layer}/{table}/data.parquet"
        destination.parent.mkdir(parents=True)
        shutil.copyfile(candidate / f"prepared/{table}.parquet", destination)
    target = candidate / "dbt-target"
    target.mkdir()
    (target / "run_results.json").write_bytes(encode({"results": [
        {"status": "success", "unique_id": f"model.caop_territory.{table}"} for table in TABLES]}))


def test_wikipedia_offline_build_and_unchanged_do_not_move_lake(tmp_path):
    root = tmp_path / "fixture"
    seed(root)
    neighbor = root / "lake/silver/other/data.parquet"
    neighbor.parent.mkdir()
    neighbor.write_bytes(b"neighbor")
    result = build(root, dbt_runner=controlled_exports)
    assert result["status"] == "promoted", result
    assert result["readiness"]["counts"] == {"valid": 2}
    before = output_hashes(root)
    times = {str(p): p.stat().st_mtime_ns for relative in PROMOTED for p in (root / relative).rglob("*") if p.is_file()}
    again = build(root, dbt_runner=controlled_exports)
    assert again["status"] == "unchanged", again
    assert output_hashes(root) == before and neighbor.read_bytes() == b"neighbor"
    assert all(Path(p).stat().st_mtime_ns == stamp for p, stamp in times.items())
    assert verify_current(root) == result["processing_signature"]


def test_wikipedia_input_corruption_does_not_promote(tmp_path):
    root = tmp_path / "fixture"
    manifest = seed(root)
    first = build(root, dbt_runner=controlled_exports)
    assert first["status"] == "promoted"
    before = output_hashes(root)
    raw = root / manifest["entries"][0]["files"][0]["key"]
    raw.write_bytes(b"corrupt")
    failed = build(root, dbt_runner=controlled_exports)
    assert failed["status"] == "failed" and not failed["readiness"]["ready"]
    assert output_hashes(root) == before


def test_wikipedia_changed_dependency_during_dbt_blocks_promotion(tmp_path):
    root = tmp_path / "fixture"
    seed(root)

    def change(candidate, silver):
        controlled_exports(candidate, silver)
        dimension = silver / "dim_municipality/data.parquet"
        dimension.write_bytes(dimension.read_bytes() + b"changed")

    result = build(root, dbt_runner=change)
    assert result["status"] == "failed" and "dependências" in result["error"]
    assert not (root / "lake/silver/wikipedia_article").exists()


def test_wikipedia_bad_export_or_missing_model_rejected(tmp_path):
    root = tmp_path / "fixture"
    seed(root)

    def broken(candidate, silver):
        controlled_exports(candidate, silver)
        (candidate / "lake/silver/wikipedia_article/data.parquet").unlink()

    result = build(root, dbt_runner=broken)
    assert result["status"] == "failed"
    assert not (root / "lake/silver/wikipedia_article").exists()


def candidate_files(root, build_id, content):
    candidate = root / ".build/wikipedia" / build_id
    for relative in PROMOTED:
        path = candidate / relative / "data.bin"
        path.parent.mkdir(parents=True)
        path.write_bytes(content)
    return candidate


class SimulatedCrash(BaseException):
    pass


@pytest.mark.parametrize("stage", [0, 2, 5])
def test_wikipedia_journal_recovers_abrupt_interruption(tmp_path, stage):
    candidate = candidate_files(tmp_path, "candidate", b"new")
    for relative in PROMOTED:
        destination = tmp_path / relative / "old.bin"
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"old")
    before = output_hashes(tmp_path)
    neighbor = tmp_path / "lake/silver/other.bin"
    neighbor.write_bytes(b"keep")

    def crash(index):
        if index == stage:
            raise SimulatedCrash()

    with pytest.raises(SimulatedCrash):
        promote(tmp_path, candidate, check_dependencies=lambda: True, after_move=crash)
    assert recover(tmp_path) == "rolled_back"
    assert output_hashes(tmp_path) == before and neighbor.read_bytes() == b"keep"
    assert recover(tmp_path) == "rolled_back"


def test_wikipedia_captured_failure_rolls_back_and_unknown_destination_blocks_recovery(tmp_path):
    candidate = candidate_files(tmp_path, "first", b"new")

    def fail(index):
        raise OSError("disk unavailable")

    with pytest.raises(OSError):
        promote(tmp_path, candidate, check_dependencies=lambda: True, after_move=fail)
    assert not any((tmp_path / relative).exists() for relative in PROMOTED)
    candidate = candidate_files(tmp_path, "second", b"new")

    def crash(index):
        raise SimulatedCrash()

    with pytest.raises(SimulatedCrash):
        promote(tmp_path, candidate, check_dependencies=lambda: True, after_move=crash)
    (tmp_path / PROMOTED[0] / "data.bin").write_bytes(b"unknown change")
    with pytest.raises(ValueError, match="desconhecido"):
        recover(tmp_path)


def test_wikipedia_active_lock_and_unsafe_journal_rejected(tmp_path):
    root = tmp_path / "fixture"
    seed(root)
    with source_lock(root):
        result = build(root, dbt_runner=controlled_exports)
    assert result["status"] == "failed" and "PID" in result["error"]
    journal = root / ".build/wikipedia/journal.json"
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_bytes(encode({"schema_version": 1, "build_id": "../outside"}))
    with pytest.raises(ValueError):
        recover(root)


def test_wikipedia_real_process_death_recovers_stale_lock_and_journal(tmp_path):
    import subprocess
    import sys

    root = tmp_path / "process-crash"
    root.mkdir()
    candidate_files(root, "crash", b"new")
    for relative in PROMOTED:
        path = root / relative / "old.bin"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"old")
    before = output_hashes(root)
    script = '''
import os,sys
from pathlib import Path
from pipelines.collectors.wikipedia.local import source_lock
from pipelines.collectors.wikipedia.promotion import promote
root=Path(sys.argv[1])
with source_lock(root):
    promote(root,root/'.build/wikipedia/crash',check_dependencies=lambda:True,after_move=lambda index:os._exit(19))
'''
    result = subprocess.run([sys.executable, "-c", script, str(root)],
                            cwd=Path(__file__).resolve().parents[2], capture_output=True, check=False)
    assert result.returncode == 19, result.stderr
    assert (root / ".locks/wikipedia.json").exists()
    with source_lock(root):
        assert recover(root) == "rolled_back"
    assert output_hashes(root) == before


def test_wikipedia_symlink_destination_confined(tmp_path):
    root, outside = tmp_path / "root", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    lake = root / "lake"
    try:
        lake.symlink_to(outside, target_is_directory=True)
    except OSError:
        # Windows sem privilégio de symlink: testar junction nativa, sem pular.
        import subprocess
        created = subprocess.run(["cmd", "/c", "mklink", "/J", str(lake), str(outside)], capture_output=True, check=False)
        assert created.returncode == 0
    result = build(root, dbt_runner=controlled_exports)
    assert result["status"] == "failed" and not list(outside.iterdir())


def test_wikipedia_absence_and_empty_typed_tables(tmp_path):
    root = tmp_path / "fixture"
    seed(root, absent=True)
    result = build(root, dbt_runner=controlled_exports)
    assert result["status"] == "promoted" and result["readiness"]["counts"] == {"valid": 1, "absent": 1}
    import pyarrow.parquet as pq
    assert pq.read_schema(root / "lake/silver/wikipedia_block/data.parquet") == SCHEMAS["wikipedia_block"]


def test_wikipedia_explicit_older_run_does_not_resolve_latest_failure(tmp_path):
    root = tmp_path / "fixture"
    previous = seed(root)
    storage = LocalStorage(root)
    fetch, _ = fetcher(failures={"0001"})
    failed = collect_wikipedia(catalog(), municipalities=municipalities(), associations=associations(),
        territory_hash=previous["territory_hash"], storage=storage, fetcher=fetch, run_id="failed",
        collected_at_utc="2026-11-20T11:00:00Z", work_dir=root / "failed-work")
    assert failed["status"] == "partial"
    default = build(root, dbt_runner=controlled_exports)
    assert default["status"] == "failed"
    selected = build(root, run_id="fixture", dbt_runner=controlled_exports)
    assert selected["status"] == "promoted" and selected["selected_older"]
    assert selected["latest_status"] == "partial" and selected["latest_run_id"] == "failed"
