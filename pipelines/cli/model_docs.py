"""CLI que gera ou confere `.docs/modelo_de_dados.md` (spec 010, US1; `contracts/cli.md` §1).

Códigos de saída: 0 ok; 1 documento ausente/defasado em `--check` ou manifest inconsistente; 2 uso, `dbt` ausente ou
falha do `dbt parse`.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from pipelines.modeldocs.model import ModelError, load_model, run_dbt_parse
from pipelines.modeldocs.render import (
    REGENERATE_COMMAND,
    load_sources_info,
    render_markdown,
)

ROOT = Path(__file__).resolve().parents[2]
DBT_PROJECT = ROOT / "analytics" / "dbt"
DEFAULT_OUTPUT = ROOT / ".docs" / "modelo_de_dados.md"
DEFAULT_SOURCES = ROOT / "config" / "sources.yml"


def _normalize(text: str) -> str:
    """O Git do Windows converte o arquivo para CRLF no checkout; a conferência ignora isso."""
    return text.replace("\r\n", "\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipelines.cli.model_docs", description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="só confere se o documento está atualizado; não grava")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="documento Markdown")
    parser.add_argument("--manifest", type=Path, help="manifest.json do dbt já pronto (sem rodar `dbt parse`)")
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES, help="config/sources.yml")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Gera (ou, com `--check`, confere) o documento do modelo de dados."""
    args = _parser().parse_args(argv)
    try:
        if args.manifest:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        else:
            with tempfile.TemporaryDirectory(prefix="model-docs-") as target:
                manifest = run_dbt_parse(DBT_PROJECT, DBT_PROJECT, Path(target))
        model = load_model(manifest)
    except ModelError as error:
        print(f"Modelo de dados inconsistente: {error}", file=sys.stderr)
        return 1
    except (RuntimeError, OSError, ValueError) as error:
        print(f"Não foi possível ler o modelo do dbt: {error}", file=sys.stderr)
        return 2
    document = render_markdown(model, load_sources_info(args.sources))
    if args.check:
        current = _normalize(args.output.read_text(encoding="utf-8")) if args.output.exists() else None
        if current != document:
            print(f"{_display(args.output)} está desatualizado. Rode: {REGENERATE_COMMAND}", file=sys.stderr)
            return 1
        print(f"{_display(args.output)} está atualizado.")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(document)
    print(f"Modelo de dados: {len(model.tables)} tabelas, {len(model.relationships)} relacionamentos -> "
          f"{_display(args.output)}")
    return 0


def _display(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
