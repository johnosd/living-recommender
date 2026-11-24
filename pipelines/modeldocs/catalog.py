"""Catálogo DuckDB único sobre o lake (spec 010, `data-model.md` §2).

Views sobre os parquets (nada é copiado), tabelas `meta.*` com o modelo do dbt e o inventário do `raw/` pelos manifests.
O lake e os manifests só são lidos: nenhum arquivo deles é aberto para escrita.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from pipelines.modeldocs.model import UNKNOWN, DataModel, Table

LAYERS = ("bronze", "silver")
DATE_KEYS = ("collected_at_utc", "checked_at_utc", "imported_at_utc")
STATUS_OK, STATUS_MISSING, STATUS_NO_MODEL = "ok", "nao_construida", "sem_modelo"

SCHEMA = """
create schema bronze; create schema silver; create schema meta;
create table meta.tables (layer varchar, table_name varchar, domain varchar, kind varchar, status varchar,
    description varchar, source_ids varchar[], row_count bigint);
create table meta.columns (layer varchar, table_name varchar, column_name varchar, position integer,
    type_actual varchar, type_declared varchar, declared boolean, in_lake boolean, description varchar,
    tests varchar[]);
create table meta.relationships (from_table varchar, from_column varchar, to_table varchar, to_column varchar,
    origin_file varchar);
create table meta.raw_runs (source_id varchar, run_id varchar, status varchar, collected_at_utc varchar,
    license_id varchar, reference_period varchar, checksums varchar[], manifest_file varchar);
"""


@dataclass(frozen=True)
class CatalogResult:
    output: Path
    # chave "<camada>.<tabela>" -> "ok" | "nao_construida" | "sem_modelo"
    tables: dict[str, str]
    raw_runs: int  # manifests lidos para o inventário
    ignored: tuple[str, ...] = field(default=())  # entradas do lake que não são tabelas (CSV, pastas de relatório)
    manifests_ignored: tuple[str, ...] = field(default=())  # manifests ilegíveis, fora do inventário


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _literal(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _scan_lake(lake_root: Path) -> tuple[dict[tuple[str, str], Path], list[str]]:
    """(camada, tabela) -> parquet, e o que não é tabela: arquivos soltos e pastas sem `data.parquet`."""
    found: dict[tuple[str, str], Path] = {}
    ignored: list[str] = []
    lake_root = lake_root.resolve()  # as views guardam caminho absoluto: o cliente SQL não roda na raiz do repositório
    for layer in LAYERS:
        folder = lake_root / layer
        if not folder.is_dir():
            continue
        for entry in sorted(folder.iterdir()):
            parquet = entry / "data.parquet"
            if entry.is_dir() and parquet.is_file():
                found[(layer, entry.name)] = parquet
            else:
                ignored.append(f"{layer}/{entry.name}")
    return found, ignored


def _sha_values(node: object) -> list[str]:
    """Todo valor de chave `sha256` (ou `*_sha256`) em qualquer profundidade, sem repetição, na ordem de aparição."""
    values: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, str) and (key == "sha256" or key.endswith("_sha256")):
                values.append(value)
            else:
                values.extend(_sha_values(value))
    elif isinstance(node, list):
        for item in node:
            values.extend(_sha_values(item))
    return list(dict.fromkeys(values))


def _raw_runs(manifests_root: Path) -> tuple[list[tuple], list[str]]:
    rows: list[tuple] = []
    ignored: list[str] = []
    for path in sorted(manifests_root.glob("*/*.json")) if manifests_root.is_dir() else []:
        relative = path.relative_to(manifests_root).as_posix()
        try:
            body = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            body = None
        if not isinstance(body, dict):
            ignored.append(relative)
            continue
        collected = next((str(body[key]) for key in DATE_KEYS if body.get(key)), None)
        rows.append((str(body.get("source_id") or path.parent.name), str(body.get("run_id") or path.stem),
                     body.get("status"), collected, body.get("license_id"), body.get("reference_period"),
                     _sha_values(body), relative))
    return rows, ignored


def _real_columns(connection: duckdb.DuckDBPyConnection, parquet: Path) -> list[tuple[str, str]]:
    rows = connection.execute(f"describe select * from read_parquet({_literal(parquet.as_posix())})").fetchall()
    # Colunas inteiramente nulas vêm como `"NULL"` (palavra reservada entre aspas); o nome do tipo é `NULL`.
    return [(row[0], row[1].strip('"')) for row in rows]


def _resolve(table: Table, found: dict[tuple[str, str], Path]) -> tuple[str, Path | None]:
    """Camada e parquet do modelo; um modelo de camada `n/d` procura nas duas camadas."""
    candidates = [table.layer] if table.layer in LAYERS else list(LAYERS)
    for layer in candidates:
        if (layer, table.name) in found:
            return layer, found[(layer, table.name)]
    return table.layer, None


def _fill(connection: duckdb.DuckDBPyConnection, model: DataModel, found: dict[tuple[str, str], Path]) -> dict:
    statuses: dict[str, str] = {}
    claimed: set[tuple[str, str]] = set()
    entries: list[tuple[str, str, Table | None, Path | None]] = []
    for table in model.tables:
        layer, parquet = _resolve(table, found)
        if parquet is not None:
            claimed.add((layer, table.name))
        entries.append((layer, table.name, table, parquet))
    entries.extend((layer, name, None, parquet) for (layer, name), parquet in sorted(found.items())
                   if (layer, name) not in claimed)
    for layer, name, table, parquet in entries:
        status = STATUS_OK if parquet is not None and table is not None else (
            STATUS_NO_MODEL if parquet is not None else STATUS_MISSING)
        statuses[f"{layer}.{name}"] = status
        row_count = None
        real: list[tuple[str, str]] = []
        if parquet is not None:
            connection.execute(f"create view {_quote(layer)}.{_quote(name)} as select * from "
                               f"read_parquet({_literal(parquet.as_posix())})")
            row_count = connection.execute(
                f"select count(*) from read_parquet({_literal(parquet.as_posix())})").fetchone()[0]
            real = _real_columns(connection, parquet)
        connection.execute("insert into meta.tables values (?, ?, ?, ?, ?, ?, ?, ?)", [
            layer, name, table.domain if table else UNKNOWN, table.kind if table else UNKNOWN, status,
            table.description if table else None, list(table.source_ids) if table else [], row_count])
        declared = {c.name: c for c in table.columns} if table else {}
        actual = {column: (position, kind) for position, (column, kind) in enumerate(real, start=1)}
        for column in [*actual, *(c for c in declared if c not in actual)]:
            info = declared.get(column)
            position, kind = actual.get(column, (None, None))
            connection.execute("insert into meta.columns values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [
                layer, name, column, position, kind, info.data_type if info else None, info is not None,
                column in actual, info.description if info else None, list(info.tests) if info else []])
    return statuses


def _insert_many(connection: duckdb.DuckDBPyConnection, table: str, rows: list[list]) -> None:
    """`executemany` do DuckDB recusa lista vazia."""
    if rows:
        placeholders = ", ".join("?" * len(rows[0]))
        connection.executemany(f"insert into {table} values ({placeholders})", rows)


def build_catalog(model: DataModel, *, lake_root: Path, manifests_root: Path, output: Path) -> CatalogResult:
    """Gera `output` (um arquivo DuckDB) sem alterar nada em `lake_root` nem em `manifests_root`.

    `lake_root` é a pasta que contém `bronze/` e `silver/` (ex.: `.data/lake`); `manifests_root` é a que contém
    `<source_id>/<run_id>.json` (ex.: `.data/manifests`). O arquivo é montado ao lado e trocado por `os.replace`: se a
    troca falhar (cliente SQL com o arquivo aberto no Windows), o catálogo anterior continua intacto.
    """
    found, ignored = _scan_lake(lake_root)
    runs, bad_manifests = _raw_runs(manifests_root)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    for stale in (temporary, temporary.with_name(temporary.name + ".wal")):
        stale.unlink(missing_ok=True)
    connection = duckdb.connect(str(temporary))
    try:
        connection.execute(SCHEMA)
        statuses = _fill(connection, model, found)
        _insert_many(connection, "meta.relationships", [
            [r.from_table, r.from_column, r.to_table, r.to_column, r.origin_file] for r in model.relationships])
        _insert_many(connection, "meta.raw_runs", [list(r) for r in runs])
    except BaseException:
        connection.close()
        temporary.unlink(missing_ok=True)
        raise
    connection.close()
    try:
        os.replace(temporary, output)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise
    return CatalogResult(output=output, tables=statuses, raw_runs=len(runs), ignored=tuple(ignored),
                         manifests_ignored=tuple(bad_manifests))
