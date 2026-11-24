"""Renderização do `.docs/modelo_de_dados.md` (spec 010, `logic/documento.md` §3 a §6).

Função pura do `DataModel` e das licenças de `config/sources.yml`: mesmas entradas, mesmos bytes. O documento não leva
data, caminho local, `run_id` nem valor de dado (FR-005, FR-006).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from pipelines.modeldocs.model import UNKNOWN, DataModel, Relationship, Table

REGENERATE_COMMAND = "uv run --locked python -m pipelines.cli.model_docs"
TERRITORIAL_KEYS = ("dico", "dicofre")
LAYERS = ("bronze", "silver")
NO_DESCRIPTION = "sem descrição"
NO_GAPS = "Nenhuma."


def load_sources_info(path: Path) -> dict[str, dict]:
    """Lê `config/sources.yml` e devolve `{source_id: {"license_id": ..., "attribution": ...}}`."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        str(key): {"license_id": (entry or {}).get("license_id"), "attribution": (entry or {}).get("attribution")}
        for key, entry in (raw.get("sources") or {}).items()}


def _inline(text: str) -> str:
    """Uma linha só e sem `|` solto, para caber numa célula de tabela Markdown sem barra invertida."""
    return re.sub(r"\s+", " ", text).strip().replace("|", "&#124;")


def _percent(done: int, total: int) -> str:
    """`n/d (p%)`, com a metade arredondada para cima; `n/d` quando não há o que contar."""
    if total == 0:
        return UNKNOWN
    return f"{done}/{total} ({(200 * done + total) // (2 * total)}%)"


def _share(done: int, total: int) -> str:
    return UNKNOWN if total == 0 else f"{(200 * done + total) // (2 * total)}%"


def _coverage(tables: list[Table]) -> tuple[int, int, int, int]:
    described = sum(1 for t in tables if t.description)
    columns = [c for t in tables for c in t.columns]
    return described, len(tables), sum(1 for c in columns if c.description), len(columns)


def _summary(model: DataModel) -> list[str]:
    by_layer = {layer: sum(1 for t in model.tables if t.layer == layer) for layer in LAYERS}
    other = len(model.tables) - sum(by_layer.values())
    parts = [f"{layer} {count}" for layer, count in by_layer.items()] + ([f"{UNKNOWN} {other}"] if other else [])
    tables_done, tables_total, columns_done, columns_total = _coverage(list(model.tables))
    return ["## Resumo", "",
            f"- Tabelas: {len(model.tables)} ({', '.join(parts)})",
            f"- Relacionamentos declarados: {len(model.relationships)}",
            "- Cobertura de descrição: tabelas "
            + f"{_share(tables_done, tables_total)}, colunas {_share(columns_done, columns_total)}"]


def _mermaid_type(data_type: str | None) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", data_type.lower()) if data_type else "n_d"


def _diagram(model: DataModel) -> list[str]:
    lines = ["## Diagrama de relacionamentos", "", "```mermaid", "erDiagram"]
    used: dict[str, set[str]] = {}
    for rel in model.relationships:
        lines.append(f'    {rel.from_table} }}o--|| {rel.to_table} : "{rel.from_column} -> {rel.to_column}"')
        used.setdefault(rel.from_table, set()).add(rel.from_column)
        used.setdefault(rel.to_table, set()).add(rel.to_column)
    tables = {t.name: t for t in model.tables}
    for name in sorted(used):
        types = {c.name: c.data_type for c in tables[name].columns} if name in tables else {}
        lines.append(f"    {name} {{")
        lines.extend(f"        {_mermaid_type(types.get(column))} {column}" for column in sorted(used[name]))
        lines.append("    }")
    lines.append("```")
    return lines


def _territorial_gaps(model: DataModel) -> list[str]:
    linked = {(r.from_table, r.from_column) for r in model.relationships}
    gaps = []
    for table in model.tables:
        for column in table.columns:
            own_key = "unique" in column.tests and "not_null" in column.tests
            if column.name in TERRITORIAL_KEYS and (table.name, column.name) not in linked and not own_key:
                gaps.append(f"{table.name}.{column.name}")
    return sorted(gaps)


def _gaps(model: DataModel) -> list[str]:
    rows = []
    for label, scope in [*((layer, [t for t in model.tables if t.layer == layer]) for layer in LAYERS),
                         ("total", list(model.tables))]:
        t_done, t_total, c_done, c_total = _coverage(scope)
        rows.append(f"| {label} | {_percent(t_done, t_total)} | {_percent(c_done, c_total)} |")
    missing = sorted(t.name for t in model.tables if not t.description) + sorted(
        f"{t.name}.{c.name}" for t in model.tables for c in t.columns if not c.description)
    territorial = _territorial_gaps(model)

    def bullets(items: list[str]) -> list[str]:
        return [f"- {item}" for item in items] if items else [NO_GAPS]

    return ["## Lacunas", "", "### Cobertura de descrição", "",
            "| Camada | Tabelas com descrição | Colunas com descrição |", "| --- | --- | --- |", *rows, "",
            "### Sem descrição", "", *bullets(missing), "",
            "### Chaves territoriais sem relacionamento declarado", "", *bullets(territorial)]


def _sources_line(table: Table, sources: dict[str, dict]) -> str:
    if not table.source_ids:
        return "não declaradas"
    items = []
    for source_id in table.source_ids:
        info = sources.get(source_id)
        if info is None or not info.get("license_id"):
            items.append(f"{source_id} (licença não declarada)")
            continue
        text = f"{source_id} ({info['license_id']})"
        if info.get("attribution"):
            text += f' — atribuição: "{_inline(str(info["attribution"]))}"'
        items.append(text)
    return "; ".join(items)


def _table_section(table: Table, outgoing: list[Relationship], sources: dict[str, dict]) -> list[str]:
    lines = [f"### {table.name}", "",
             f"- Camada: {table.layer} | Domínio: {table.domain} | Tipo: {table.kind}",
             f"- Fontes: {_sources_line(table, sources)}",
             f"- Descrição: {_inline(table.description) if table.description else NO_DESCRIPTION}"]
    if table.kind == "relatorio":
        lines.append("- Observação: as colunas listadas são só as declaradas no schema.yml; a lista pode estar "
                     "incompleta.")
    lines.append("")
    if table.columns:
        lines += ["| Coluna | Tipo | Descrição | Testes |", "| --- | --- | --- | --- |"]
        lines.extend(
            f"| {c.name} | {c.data_type or UNKNOWN} | {_inline(c.description) if c.description else NO_DESCRIPTION} "
            f"| {', '.join(c.tests) or '—'} |" for c in table.columns)
    else:
        lines.append("Colunas declaradas: nenhuma.")
    if outgoing:
        lines += ["", "Relacionamentos:", ""]
        lines.extend(f"- `{r.from_column}` -> `{r.to_table}.{r.to_column}`" for r in outgoing)
    return lines


def render_markdown(model: DataModel, sources: dict[str, dict]) -> str:
    """Texto completo do documento, determinístico: mesmas entradas, mesmos bytes (FR-005)."""
    outgoing: dict[str, list[Relationship]] = {}
    for rel in model.relationships:
        outgoing.setdefault(rel.from_table, []).append(rel)
    blocks = [
        ["# Modelo de dados", "",
         f"> Arquivo gerado por `{REGENERATE_COMMAND}`. Não edite à mão: o CI reprova se ele",
         "> divergir dos `schema.yml` do dbt."],
        _summary(model), _diagram(model), _gaps(model),
        ["## Dicionário de dados"],
    ]
    blocks.extend(_table_section(table, outgoing.get(table.name, []), sources) for table in model.tables)
    return "\n\n".join("\n".join(block) for block in blocks) + "\n"
