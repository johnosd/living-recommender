"""Modelo de dados lido do manifest do dbt (spec 010, `logic/documento.md` §1 e §2).

Tudo aqui é função pura do `manifest.json` (já lido como dict), exceto `run_dbt_parse`, que gera esse manifest sem banco
e sem lake. O resultado não depende da ordem dos nós nem do sistema operacional.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

PROJECT_PREFIX = "analytics/dbt/"
LAYER_PATTERN = re.compile(r"/lake/(bronze|silver|gold)/")
REFERENCE_PATTERN = re.compile(r"^\s*(ref|source)\s*\((?P<args>[^)]*)\)\s*$")
QUOTED_PATTERN = re.compile(r"""['"]([^'"]+)['"]""")
REPORT_PREFIX = "rpt_"
REPORT_SUFFIX = "_coverage"
UNKNOWN = "n/d"


class ModelError(Exception):
    """Manifest inconsistente. A mensagem DEVE nomear o arquivo yml, o modelo e o destino (FR-009)."""


@dataclass(frozen=True)
class Column:
    name: str
    data_type: str | None
    description: str | None
    tests: tuple[str, ...]  # nomes dos testes dbt da coluna, ordenados e sem repetição


@dataclass(frozen=True)
class Table:
    name: str
    unique_id: str
    layer: str  # "bronze" | "silver" | "n/d"
    domain: str  # primeira tag do modelo (ex.: "mobility"); "n/d" se não houver
    kind: str  # "relatorio" (rpt_* ou *_coverage) | "principal"
    description: str | None
    columns: tuple[Column, ...]  # só as colunas declaradas no schema.yml, na ordem declarada
    source_ids: tuple[str, ...]  # `meta.source_ids` do modelo; vazio quando não declarado
    origin_file: str  # yml relativo ao repositório (ex.: "analytics/dbt/models/mobility/schema.yml")


@dataclass(frozen=True)
class Relationship:
    from_table: str
    from_column: str
    to_table: str  # sempre o nome de um modelo (uma fonte `caop_silver.X` resolve para o modelo `X`)
    to_column: str
    origin_file: str


@dataclass(frozen=True)
class DataModel:
    tables: tuple[Table, ...]  # ordenadas por (layer, domain, name)
    relationships: tuple[Relationship, ...]  # ordenadas por (from_table, from_column, to_table, to_column)


def _text(value: object) -> str | None:
    """O dbt grava `''` quando falta descrição: aqui isso vira `None`."""
    return (value.strip() or None) if isinstance(value, str) else None


def _repo_path(path: str | None) -> str:
    """Caminho do yml relativo ao repositório, sempre com `/` (o manifest do Windows traz `\\`)."""
    if not path:
        return UNKNOWN
    path = re.sub(r"^[A-Za-z0-9_]+://", "", path).replace("\\", "/")
    return path if path.startswith(PROJECT_PREFIX) else PROJECT_PREFIX + path


def _origin(node: dict) -> str:
    return _repo_path(node.get("patch_path") or node.get("original_file_path"))


def _kind(name: str) -> str:
    return "relatorio" if name.startswith(REPORT_PREFIX) or name.endswith(REPORT_SUFFIX) else "principal"


def _layer(node: dict) -> str:
    location = str((node.get("config") or {}).get("location") or "").replace("\\", "/")
    match = LAYER_PATTERN.search(location)
    return match.group(1) if match else UNKNOWN


def _column_tests(nodes: list[dict]) -> dict[tuple[str, str], tuple[str, ...]]:
    """(unique_id do modelo, coluna) -> nomes dos testes genéricos. Testes singulares não têm `test_metadata`."""
    found: dict[tuple[str, str], set[str]] = {}
    for node in nodes:
        metadata = node.get("test_metadata")
        if node.get("resource_type") != "test" or not metadata or not node.get("column_name"):
            continue
        found.setdefault((node["attached_node"], node["column_name"]), set()).add(metadata["name"])
    return {key: tuple(sorted(names)) for key, names in found.items()}


def _table(node: dict, tests: dict[tuple[str, str], tuple[str, ...]]) -> Table:
    tags = node.get("tags") or []
    columns = tuple(
        Column(name=name, data_type=_text(info.get("data_type")), description=_text(info.get("description")),
               tests=tests.get((node["unique_id"], name), ()))
        for name, info in (node.get("columns") or {}).items())
    return Table(
        name=node["name"], unique_id=node["unique_id"], layer=_layer(node), domain=tags[0] if tags else UNKNOWN,
        kind=_kind(node["name"]), description=_text(node.get("description")), columns=columns,
        source_ids=tuple((node.get("meta") or {}).get("source_ids") or ()), origin_file=_origin(node))


def _target(expression: str) -> str:
    """`ref('x')` -> "x"; `source('s', 't')` -> "t"; qualquer outra forma -> "" (não resolvida)."""
    match = REFERENCE_PATTERN.match(expression or "")
    names = QUOTED_PATTERN.findall(match.group("args")) if match else []
    return names[-1] if names else ""


def _relationships(nodes: list[dict], tables: dict[str, Table]) -> list[Relationship]:
    by_id = {table.unique_id: table for table in tables.values()}
    found: list[Relationship] = []
    for node in nodes:
        metadata = node.get("test_metadata") or {}
        if node.get("resource_type") != "test" or metadata.get("name") != "relationships":
            continue
        source = by_id.get(node.get("attached_node"))
        kwargs = metadata.get("kwargs") or {}
        target = _target(str(kwargs.get("to") or ""))
        if source is None or target not in tables:
            owner = source.name if source else str(node.get("attached_node"))
            raise ModelError(
                f"{_origin(node)}: o modelo {owner} aponta `{node.get('column_name')}` para {kwargs.get('to')}, "
                f"que não corresponde a nenhum modelo ({target or 'alvo ilegível'})")
        found.append(Relationship(from_table=source.name, from_column=str(node["column_name"]), to_table=target,
                                  to_column=str(kwargs.get("field")), origin_file=_origin(node)))
    return sorted(found, key=lambda r: (r.from_table, r.from_column, r.to_table, r.to_column))


def load_model(manifest: dict) -> DataModel:
    """Converte o `manifest.json` do dbt (já lido como dict) em `DataModel`. Determinística e sem rede."""
    nodes = list((manifest.get("nodes") or {}).values())
    tests = _column_tests(nodes)
    tables = {node["name"]: _table(node, tests) for node in nodes if node.get("resource_type") == "model"}
    ordered = tuple(sorted(tables.values(), key=lambda t: (t.layer, t.domain, t.name)))
    return DataModel(tables=ordered, relationships=tuple(_relationships(nodes, tables)))


def run_dbt_parse(project_dir: Path, profiles_dir: Path, target_path: Path, *, target: str = "local") -> dict:
    """Roda `dbt parse` (sem banco, sem lake) com `DBT_TARGET_PATH=target_path` e devolve o manifest como dict."""
    executable = shutil.which("dbt")
    if executable is None:
        raise RuntimeError("`dbt` não encontrado no PATH; rode com `uv run --locked python -m ...`")
    target_path.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "DBT_TARGET_PATH": str(target_path), "DBT_LOG_PATH": str(target_path / "logs"),
           "CAOP_DUCKDB_PATH": str(target_path / "never-opened.duckdb")}
    result = subprocess.run(
        [executable, "parse", "--project-dir", str(project_dir), "--profiles-dir", str(profiles_dir), "--target",
         target], capture_output=True, text=True, env=env, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"`dbt parse` falhou (código {result.returncode}):\n{result.stdout[-1500:]}"
                           f"\n{result.stderr[-500:]}")
    return json.loads((target_path / "manifest.json").read_text(encoding="utf-8"))
