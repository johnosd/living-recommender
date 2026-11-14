"""Coleta responsável e auditável dos Censos 2021."""

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
from pipelines.collectors._shared.catalog import load_catalog
from pipelines.collectors._shared.datasets import DatasetCollectionError
from pipelines.collectors._shared.http import (
    HttpDownloader,
    RateLimiter,
    json_content_check,
)
from pipelines.collectors.censos2021.handler import collect_censos


def main(argv=None, *, downloader=None, storage=None):
    parser = argparse.ArgumentParser(
        description="Coleta Censos 2021 por freguesia com metadados e raw imutável."
    )
    add_destination_arguments(parser)
    args = parser.parse_args(argv)
    check_destination_arguments(parser, args)
    run_id = new_run_id()
    try:
        result = collect_censos(
            load_catalog(args.catalog) if args.catalog else load_catalog(),
            storage=storage if storage is not None else make_storage(args),
            downloader=downloader
            if downloader is not None
            else HttpDownloader(
                content_check=json_content_check,
                timeout=90,
                max_attempts=3,
                backoff=2,
                rate_limiter=RateLimiter(2),
            ),
            run_id=run_id,
            collected_at_utc=utc_now(),
            work_dir=args.root / ".work" / "censos" / run_id,
        )
    except (ValueError, OSError, DatasetCollectionError) as exc:
        print(f"Censos: falha: {exc}", file=sys.stderr)
        return 1
    print_result("Censos 2021", result, args)
    return exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
