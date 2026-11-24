"""CLI que gera o catálogo DuckDB do lake (spec 010, US2; `contracts/cli.md` §2).

Códigos de saída: 0 ok (mesmo com tabelas não construídas); 1 manifest inconsistente ou arquivo de saída em uso por um
cliente SQL; 2 uso, `dbt` ausente ou falha do `dbt parse`.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

from pipelines.modeldocs.catalog import (
    STATUS_MISSING,
    STATUS_NO_MODEL,
    STATUS_OK,
    build_catalog,
)
from pipelines.modeldocs.model import ModelError, load_model, run_dbt_parse

ROOT = Path(__file__).resolve().parents[2]
DBT_PROJECT = ROOT / "analytics" / "dbt"
DEFAULT_ROOT = ROOT / ".data"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipelines.cli.lake_catalog", description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="pasta com `lake/` e `manifests/`")
    parser.add_argument("--output", type=Path, help="arquivo DuckDB de saída (padrão: <root>/catalog.duckdb)")
    parser.add_argument("--manifest", type=Path, help="manifest.json do dbt já pronto (sem rodar `dbt parse`)")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Gera o catálogo; nunca abre arquivo do lake ou dos manifests para escrita."""
    args = _parser().parse_args(argv)
    output = args.output or args.root / "catalog.duckdb"
    try:
        if args.manifest:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        else:
            with tempfile.TemporaryDirectory(prefix="lake-catalog-") as target:
                manifest = run_dbt_parse(DBT_PROJECT, DBT_PROJECT, Path(target))
        model = load_model(manifest)
    except ModelError as error:
        print(f"Modelo de dados inconsistente: {error}", file=sys.stderr)
        return 1
    except (RuntimeError, OSError, ValueError) as error:
        print(f"Não foi possível ler o modelo do dbt: {error}", file=sys.stderr)
        return 2
    try:
        result = build_catalog(model, lake_root=args.root / "lake", manifests_root=args.root / "manifests",
                               output=output)
    except OSError as error:
        print(f"Não foi possível gravar {output}: {error}. Feche o cliente SQL que está usando {output} e rode de "
              "novo; o catálogo anterior foi mantido.", file=sys.stderr)
        return 1
    status = Counter(result.tables.values())
    print(f"Catálogo: {output} ({output.stat().st_size / 1_000_000:.2f} MB)")
    print(f"Tabelas: {status[STATUS_OK]} ok, {status[STATUS_MISSING]} não construídas, "
          f"{status[STATUS_NO_MODEL]} sem modelo")
    print(f"Entradas do lake ignoradas (não são tabelas): {len(result.ignored)}")
    print(f"Manifests: {result.raw_runs} lidos, {len(result.manifests_ignored)} ignorados")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
