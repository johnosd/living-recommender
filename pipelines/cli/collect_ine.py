"""Coleta os indicadores do INE (rendas, criminalidade e poder de compra) pela API JSON."""

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
    json_content_check,
)
from pipelines.collectors.ine.handler import collect_ine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Coleta os indicadores do INE em raw imutável; um indicador com falha não bloqueia os demais.",
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
        result = collect_ine(
            catalog,
            storage=storage if storage is not None else make_storage(args),
            # A API do INE é lenta e instável (timeouts de 60 s observados): 90 s, 3 tentativas e espera crescente.
            downloader=downloader if downloader is not None else HttpDownloader(
                content_check=json_content_check, timeout=90.0, max_attempts=3, backoff=2.0,
                rate_limiter=RateLimiter(2.0),
            ),
            run_id=run_id,
            collected_at_utc=utc_now(),
            work_dir=args.root / ".work" / "ine" / run_id,
            **options,
        )
    except (CatalogError, DatasetCollectionError, OSError, ValueError) as exc:
        print(f"INE: falha: {exc}", file=sys.stderr)
        return 1
    print_result("INE", result, args)
    return exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
