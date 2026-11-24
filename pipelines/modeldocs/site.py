"""Site do `dbt docs` com lineage entre builds isolados (spec 010, US4; `logic/site.md`).

O dbt trata `source('caop_silver', 'dim_municipality')` como um nó de fonte sem ligação com o modelo
`dim_municipality`, que é produzido em outro build. `link_sources_to_models` cria essa aresta no manifest, e
`lake_catalog_json` preenche o `catalog.json` com os tipos reais do lake (só nomes e tipos, nunca valores).
"""

from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path

import duckdb

from pipelines.modeldocs.catalog import LAYERS
from pipelines.modeldocs.model import DataModel

CATALOG_SCHEMA = "https://schemas.getdbt.com/dbt/catalog/v1.json"
NO_STATS = {"has_stats": {"id": "has_stats", "label": "Has Stats?", "value": False, "include": False,
                          "description": "Indicates whether there are statistics for this table"}}


def link_sources_to_models(manifest: dict) -> dict:
    """Devolve uma cópia do manifest em que cada fonte `X.Y` com modelo homônimo `Y` ganha a aresta modelo -> fonte
    em `parent_map` e `child_map`. Não altera o dict recebido."""
    linked = copy.deepcopy(manifest)
    models = {node["name"]: unique_id for unique_id, node in (linked.get("nodes") or {}).items()
              if node.get("resource_type") == "model"}
    parent_map = linked.setdefault("parent_map", {})
    child_map = linked.setdefault("child_map", {})
    for source_id, source in (linked.get("sources") or {}).items():
        model_id = models.get(source.get("name"))
        if model_id is None:
            continue
        parents = parent_map.setdefault(source_id, [])
        if model_id not in parents:
            parents.append(model_id)
        children = child_map.setdefault(model_id, [])
        if source_id not in children:
            children.append(source_id)
    return linked


def link_relationships(manifest: dict, model: DataModel) -> dict:
    """Devolve uma cópia do manifest com a aresta `to_table` -> `from_table` para cada `relationships` declarado.

    Vários modelos leem o parquet de outro build por `read_parquet(...)`, sem `ref` nem `source`: no dbt a ligação deles
    com, por exemplo, `dim_municipality` existe só pelo nó do teste. Só a cópia do site muda; o diagrama do documento
    usa os mesmos relacionamentos (D3). Autorreferência e aresta repetida são ignoradas. Não altera o dict recebido.
    """
    linked = copy.deepcopy(manifest)
    ids = {table.name: table.unique_id for table in model.tables}
    parent_map = linked.setdefault("parent_map", {})
    child_map = linked.setdefault("child_map", {})
    for relationship in model.relationships:
        child, parent = ids.get(relationship.from_table), ids.get(relationship.to_table)
        if child is None or parent is None or child == parent:
            continue
        parents = parent_map.setdefault(child, [])
        if parent not in parents:
            parents.append(parent)
        children = child_map.setdefault(parent, [])
        if child not in children:
            children.append(child)
    return linked


def _empty_catalog(metadata: dict | None, generated_at: datetime) -> dict:
    base = copy.deepcopy(metadata) if metadata else {"dbt_schema_version": CATALOG_SCHEMA}
    base["generated_at"] = generated_at.isoformat().replace("+00:00", "Z")
    return {"metadata": base, "nodes": {}, "sources": {}, "errors": None}


def lake_catalog_json(model: DataModel, lake_root: Path, *, generated_at: datetime,
                      base: dict | None = None) -> dict:
    """`catalog.json` (schema do dbt) com colunas e tipos reais lidos dos parquets do lake; vazio se não houver lake.

    `base` é o `catalog.json` vazio que o próprio dbt gerou: dele vem o `metadata` (versão, esquema)."""
    catalog = _empty_catalog((base or {}).get("metadata"), generated_at)
    if not lake_root.is_dir():
        return catalog
    connection = duckdb.connect()
    try:
        for table in model.tables:
            layers = [table.layer] if table.layer in LAYERS else list(LAYERS)
            for layer in layers:
                parquet = lake_root / layer / table.name / "data.parquet"
                if not parquet.is_file():
                    continue
                quoted = parquet.as_posix().replace("'", "''")
                rows = connection.execute(f"describe select * from read_parquet('{quoted}')").fetchall()
                columns = {name: {"type": kind.strip('"'), "index": position, "name": name, "comment": None}
                           for position, (name, kind, *_rest) in enumerate(rows, start=1)}
                catalog["nodes"][table.unique_id] = {
                    "metadata": {"type": "BASE TABLE", "schema": layer, "name": table.name, "database": None,
                                 "comment": None, "owner": None},
                    "columns": columns, "stats": copy.deepcopy(NO_STATS), "unique_id": table.unique_id}
                break
    finally:
        connection.close()
    return catalog
