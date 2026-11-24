"""Lake e manifests de coleta minúsculos para os contratos do catálogo (spec 010; travado com os contratos)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


def write_table(lake_root: Path, layer: str, name: str, columns: dict[str, list]) -> Path:
    path = lake_root / layer / name / "data.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table(columns), path)
    return path


def write_manifest(manifests_root: Path, source_id: str, run_id: str, **fields) -> Path:
    path = manifests_root / source_id / f"{run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"schema_version": 1, "source_id": source_id, "run_id": run_id, "status": "changed",
            "license_id": "CC-BY-4.0", **fields}
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def snapshot(root: Path) -> dict[str, str]:
    """Hash de cada arquivo sob `root`, para provar que nada foi alterado."""
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}
