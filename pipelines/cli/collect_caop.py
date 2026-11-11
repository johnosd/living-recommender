"""Coleta a CAOP vigente em storage local."""

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pipelines.collectors._shared.catalog import CatalogError, load_catalog
from pipelines.collectors._shared.http import HttpDownloader
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors._shared.storage_s3 import S3Storage
from pipelines.collectors.caop.handler import CollectionError, collect_caop
from pipelines.collectors.caop.schema import validate_caop_archive


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Coleta os três ZIPs da CAOP em raw imutável.")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument("--local", action="store_true", help="destino local (padrão)")
    destination.add_argument(
        "--s3", action="store_true",
        help="destino S3; credenciais pela cadeia padrão da AWS, nunca por arquivo versionado",
    )
    parser.add_argument("--bucket", help="bucket S3 (obrigatório com --s3)")
    parser.add_argument("--prefix", default="", help="prefixo opcional dentro do bucket S3")
    parser.add_argument(
        "--root", type=Path, default=Path(".data"),
        help="raiz local (padrão: .data); com --s3 guarda só os arquivos temporários",
    )
    parser.add_argument(
        "--force-check", action="store_true",
        help="repete a verificação da fonte; checksum igual continua unchanged",
    )
    parser.add_argument(
        "--catalog", type=Path, default=None,
        help="caminho do catálogo YAML (padrão: config/sources.yml)",
    )
    return parser


def main(
    argv: list[str] | None = None,
    *,
    downloader=None,
    validator=None,
    storage=None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.s3 and not args.bucket:
        parser.error("--s3 exige --bucket")
    if (args.bucket or args.prefix) and not args.s3:
        parser.error("--bucket e --prefix só valem com --s3")
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:8]
    collected_at_utc = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    try:
        catalog = load_catalog(args.catalog) if args.catalog else load_catalog()
        if storage is not None:
            target = storage
        elif args.s3:
            target = S3Storage(args.bucket, args.prefix)
        else:
            target = LocalStorage(args.root)
        result = collect_caop(
            catalog,
            storage=target,
            downloader=downloader if downloader is not None else HttpDownloader(),
            validator=validator if validator is not None else validate_caop_archive,
            run_id=run_id,
            collected_at_utc=collected_at_utc,
            work_dir=args.root / ".work" / "caop" / run_id,
        )
    except (CatalogError, CollectionError, OSError, ValueError) as exc:
        print(f"CAOP: falha: {exc}", file=sys.stderr)
        return 1
    print(f"CAOP {result['version']}: {result['status']} | run_id={result['run_id']}")
    for entry in result["files"]:
        print(f"  {entry['region']}: {entry['key']} ({entry['bytes']} bytes)")
    print(f"  manifest: {result['manifest_key']}")
    if args.s3:
        print(f"  destino: s3://{args.bucket}/{args.prefix.strip('/')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
