"""Coleta as duas planilhas de correspondência de freguesias do INE; uma tabela com falha não bloqueia a outra."""

import argparse
import sys

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
from pipelines.collectors._shared.http import (
    HttpDownloader,
    RateLimiter,
    xlsx_content_check,
)
from pipelines.collectors.parish_crosswalk.handler import collect_parish_crosswalk


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Coleta as tabelas de correspondência de freguesias do INE em raw imutável; "
                    "uma tabela com falha não bloqueia a outra.",
    )
    add_destination_arguments(parser)
    return parser


def main(argv: list[str] | None = None, *, downloader=None, validator=None, storage=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    check_destination_arguments(parser, args)
    run_id = new_run_id()
    try:
        catalog = load_catalog(args.catalog) if args.catalog else load_catalog()
        options = {"validator": validator} if validator is not None else {}
        result = collect_parish_crosswalk(
            catalog,
            storage=storage if storage is not None else make_storage(args),
            downloader=downloader if downloader is not None else HttpDownloader(
                content_check=xlsx_content_check, timeout=120.0, rate_limiter=RateLimiter(1.0),
            ),
            run_id=run_id,
            collected_at_utc=utc_now(),
            work_dir=args.root / ".work" / "ine_parish_crosswalk" / run_id,
            **options,
        )
    except (CatalogError, DatasetCollectionError, OSError, ValueError) as exc:
        print(f"Correspondência INE: falha: {exc}", file=sys.stderr)
        return 1
    print_result("Correspondência INE", result, args)
    return exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
