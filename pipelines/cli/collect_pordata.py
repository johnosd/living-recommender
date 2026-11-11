"""Coleta os datasets do Pordata disponíveis por HTTP, cada um com estado próprio."""

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
    csv_content_check,
)
from pipelines.collectors.pordata.handler import collect_pordata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Coleta os CSV do Pordata em raw imutável; um dataset com falha não bloqueia os demais.",
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
        result = collect_pordata(
            catalog,
            storage=storage if storage is not None else make_storage(args),
            downloader=downloader if downloader is not None else HttpDownloader(
                content_check=csv_content_check, timeout=120.0, rate_limiter=RateLimiter(1.0),
            ),
            run_id=run_id,
            collected_at_utc=utc_now(),
            work_dir=args.root / ".work" / "pordata" / run_id,
            **options,
        )
    except (CatalogError, DatasetCollectionError, OSError, ValueError) as exc:
        print(f"Pordata: falha: {exc}", file=sys.stderr)
        return 1
    print_result("Pordata", result, args)
    return exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
