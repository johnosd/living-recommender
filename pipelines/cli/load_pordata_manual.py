"""Entrega ao sistema a planilha do Pordata exportada à mão (poder de compra per capita)."""

import argparse
import sys
from pathlib import Path

from pipelines.cli._common import (
    add_destination_arguments,
    check_destination_arguments,
    exit_code,
    make_storage,
    new_run_id,
    print_result,
    utc_now,
)
from pipelines.collectors._shared.catalog import CatalogError, load_catalog
from pipelines.collectors._shared.datasets import DatasetCollectionError
from pipelines.collectors.pordata.manual import DEFAULT_DATASET, load_pordata_manual


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Guarda a planilha do Pordata exportada à mão como bruto imutável, com manifest.",
    )
    parser.add_argument("--file", type=Path, required=True, help="planilha .xlsx exportada do site do Pordata")
    parser.add_argument("--dataset", default=DEFAULT_DATASET, help=f"dataset de carga manual (padrão: {DEFAULT_DATASET})")
    add_destination_arguments(parser)
    return parser


def main(argv: list[str] | None = None, *, storage=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    check_destination_arguments(parser, args)
    if not args.file.is_file():
        print(f"Pordata (manual): falha: arquivo não encontrado: {args.file}", file=sys.stderr)
        return 1
    run_id = new_run_id()
    try:
        catalog = load_catalog(args.catalog) if args.catalog else load_catalog()
        result = load_pordata_manual(
            catalog,
            storage=storage if storage is not None else make_storage(args),
            file=args.file,
            run_id=run_id,
            collected_at_utc=utc_now(),
            work_dir=args.root / ".work" / "pordata-manual" / run_id,
            dataset_id=args.dataset,
        )
    except (CatalogError, DatasetCollectionError, OSError, ValueError) as exc:
        print(f"Pordata (manual): falha: {exc}", file=sys.stderr)
        return 1
    print_result("Pordata (manual)", result, args)
    return exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
