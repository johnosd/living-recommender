"""Manifests do dbt sintéticos e o manifest real do projeto (spec 010; travado com os contratos).

`make_manifest` imita só as chaves que o dbt 1.12 grava e que `load_model` consome, incluindo as armadilhas reais:
caminhos com barra invertida (Windows), `description` vazia em vez de `None` e testes singulares sem `test_metadata`.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

PACKAGE = "caop_territory"
ROOT = Path(__file__).resolve().parents[3]


def column(name, *, description="", data_type=None, tests=()):
    return {"name": name, "description": description, "data_type": data_type, "tests": list(tests)}


def model(name, *, layer="bronze", domain="demo", description="", columns=(), source_ids=(), yml="demo/schema.yml"):
    return {"name": name, "layer": layer, "domain": domain, "description": description, "columns": list(columns),
            "source_ids": list(source_ids), "yml": yml}


def make_manifest(models, *, relationships=(), sources=()):
    """`relationships`: tuplas (from_model, from_column, to, to_column), onde `to` é `ref:<modelo>` ou
    `source:<fonte>.<tabela>`. `sources`: nomes `fonte.tabela` declarados no dbt (alguns sem modelo homônimo)."""
    nodes, source_nodes = {}, {}
    for spec in models:
        unique_id = f"model.{PACKAGE}.{spec['name']}"
        yml = spec["yml"].replace("/", "\\")
        nodes[unique_id] = {
            "unique_id": unique_id, "name": spec["name"], "resource_type": "model", "package_name": PACKAGE,
            "tags": [spec["domain"]], "description": spec["description"], "meta": {"source_ids": spec["source_ids"]}
            if spec["source_ids"] else {},
            "original_file_path": f"models\\{spec['domain']}\\{spec['name']}.sql",
            "patch_path": f"{PACKAGE}://models\\{yml}",
            "config": {"location": f".data/ci/lake/{spec['layer']}/{spec['name']}/data.parquet", "meta": {}},
            "columns": {c["name"]: {"name": c["name"], "description": c["description"], "data_type": c["data_type"],
                                    "meta": {}, "tags": []} for c in spec["columns"]},
        }
        for c in spec["columns"]:
            for test in c["tests"]:
                test_id = f"test.{PACKAGE}.{test}_{spec['name']}_{c['name']}.0000000000"
                nodes[test_id] = _test(test_id, unique_id, c["name"], test, {}, f"models\\{yml}")
        nodes[f"test.{PACKAGE}.singular_{spec['name']}.0"] = {  # teste singular: sem test_metadata
            "unique_id": f"test.{PACKAGE}.singular_{spec['name']}.0", "resource_type": "test",
            "original_file_path": f"tests\\singular_{spec['name']}.sql", "patch_path": None}
    for name in sources:
        source_name, table = name.split(".")
        unique_id = f"source.{PACKAGE}.{source_name}.{table}"
        source_nodes[unique_id] = {"unique_id": unique_id, "name": table, "source_name": source_name,
                                   "resource_type": "source", "original_file_path": "models\\demo\\schema.yml"}
    for index, (from_model, from_column, target, to_column) in enumerate(relationships):
        spec = next(s for s in models if s["name"] == from_model)
        to = f"ref('{target[4:]}')" if target.startswith("ref:") else \
            "source('{}', '{}')".format(*target[7:].split("."))
        test_id = f"test.{PACKAGE}.relationships_{from_model}_{from_column}_{index}.0000000000"
        nodes[test_id] = _test(test_id, f"model.{PACKAGE}.{from_model}", from_column, "relationships",
                               {"to": to, "field": to_column}, f"models\\{spec['yml'].replace('/', chr(92))}")
    return {"metadata": {"dbt_version": "1.12.6", "adapter_type": "duckdb"}, "nodes": nodes,
            "sources": source_nodes, "parent_map": {}, "child_map": {}}


def _test(test_id, attached, column_name, name, kwargs, original_file_path):
    return {"unique_id": test_id, "resource_type": "test", "attached_node": attached, "column_name": column_name,
            "test_metadata": {"name": name, "namespace": None, "kwargs": {"column_name": column_name, **kwargs}},
            "original_file_path": original_file_path, "patch_path": None}


def parse_real_manifest(target_path: Path) -> dict:
    """Roda `dbt parse` de verdade no projeto (sem banco, sem lake) e lê o manifest. Independente de `run_dbt_parse`."""
    env = {**os.environ, "DBT_TARGET_PATH": str(target_path), "DBT_LOG_PATH": str(target_path / "logs"),
           "CAOP_DUCKDB_PATH": str(target_path / "never-opened.duckdb")}
    project = ROOT / "analytics" / "dbt"
    subprocess.run(["dbt", "parse", "--project-dir", str(project), "--profiles-dir", str(project), "--target",
                    "local"], check=True, capture_output=True, text=True, env=env, cwd=ROOT)
    return json.loads((target_path / "manifest.json").read_text(encoding="utf-8"))
