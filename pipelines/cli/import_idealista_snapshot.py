"""Importa uma pasta produzida manualmente pela extensão externa do Idealista."""

import argparse
import sys
from pathlib import Path

from pipelines.cli._common import (
    add_destination_arguments,
    check_destination_arguments,
    make_storage,
    new_run_id,
    utc_now,
)
from pipelines.collectors._shared.catalog import load_catalog
from pipelines.collectors.idealista.snapshot import check_local_paths, import_snapshot


def main(argv=None, *, storage=None) -> int:
    parser = argparse.ArgumentParser(description="Importa snapshot manual do Idealista; não acessa o site.")
    parser.add_argument("--directory", type=Path, required=True, help="pasta de extração (somente leitura)")
    parser.add_argument("--snapshot-month", required=True, help="período da extração, YYYY-MM")
    add_destination_arguments(parser)
    args = parser.parse_args(argv)
    check_destination_arguments(parser, args)
    try:
        if storage is None and not args.s3:
            check_local_paths(args.directory, args.root)
        result = import_snapshot(load_catalog(args.catalog) if args.catalog else load_catalog(),
                                 storage=storage if storage is not None else make_storage(args),
                                 directory=args.directory, snapshot_month=args.snapshot_month,
                                 run_id=new_run_id(), imported_at_utc=utc_now())
    except (OSError, ValueError) as exc:
        print(f"Idealista: falha: {exc}", file=sys.stderr)
        return 1
    print(f"Idealista: {result['status']} | período={result['snapshot_month']} | run_id={result['run_id']}")
    print(f"  {len(result['files'])} arquivos | {result['records']} ocorrências | coleta original: horário desconhecido")
    print(f"  manifest: {result['manifest_key']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
