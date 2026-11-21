"""Nome CAOP preservado nos relatórios, inclusive nas unidades sem artigo válido."""

import csv

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors.wikipedia.handler import collect_wikipedia
from pipelines.collectors.wikipedia.local import file_hash
from pipelines.collectors.wikipedia.prepare import prepare_wikipedia
from tests.fixtures.wikipedia.ci_seed import seed
from tests.fixtures.wikipedia.responses import catalog, fetcher, municipalities


@pytest.mark.parametrize("status", ["valid", "absent", "pending", "failed", "identity_pending"])
def test_wikipedia_coverage_official_name_comes_from_dimension_for_every_status(tmp_path, status):
    root = tmp_path / "fixture"
    initial = seed(root, absent=status == "absent")
    dimension_path = root / "lake/silver/dim_municipality/data.parquet"
    territory = municipalities()
    territory[1]["official_name"] = "Nome oficial municipal da Beta"
    pq.write_table(pa.Table.from_pylist(territory), dimension_path)
    fetch, _ = fetcher()
    storage = LocalStorage(root)
    manifest = collect_wikipedia(catalog(), municipalities=territory,
        associations=initial["associations_snapshot"], territory_hash=file_hash(dimension_path),
        storage=storage, fetcher=fetch, run_id="names", collected_at_utc="2026-11-20T12:00:00Z",
        work_dir=root / "names-work")
    if status in {"pending", "failed", "identity_pending"}:
        entry = manifest["entries"][1]
        entry.update(status="pending" if status == "pending" else "failed", files=[],
                     reason="identity_pending" if status == "identity_pending" else "source_wait")
        manifest["status"] = "partial"
    candidate = root / "candidate"
    prepare_wikipedia(storage, manifest, candidate, dimension_path)
    table = pq.read_table(candidate / "prepared/wikipedia_coverage.parquet").to_pylist()
    coverage = next(row for row in table if row["dico"] == "0002")
    assert coverage["official_name"] == territory[1]["official_name"]
    assert coverage["status"] == status
    with (candidate / "lake/silver/wikipedia_reports/coverage.csv").open(encoding="utf-8-sig", newline="") as stream:
        csv_row = next(row for row in csv.DictReader(stream, delimiter=";") if row["dico"] == "0002")
    assert csv_row["official_name"] == territory[1]["official_name"]
    assert csv_row["official_name"] != csv_row["canonical_title"]
