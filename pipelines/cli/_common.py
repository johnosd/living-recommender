"""Pedaços compartilhados pelas CLIs de coleta por dataset (Pordata, INE e carga manual).

A `collect_caop` mantém o seu próprio parser: a CAOP não foi alterada nesta feature.
"""

import argparse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors._shared.storage_s3 import S3Storage

OK_STATUSES = {"changed", "unchanged"}


def add_destination_arguments(parser: argparse.ArgumentParser) -> None:
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
        "--catalog", type=Path, default=None, help="caminho do catálogo YAML (padrão: config/sources.yml)",
    )


def check_destination_arguments(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.s3 and not args.bucket:
        parser.error("--s3 exige --bucket")
    if (args.bucket or args.prefix) and not args.s3:
        parser.error("--bucket e --prefix só valem com --s3")


def make_storage(args: argparse.Namespace) -> Any:
    return S3Storage(args.bucket, args.prefix) if args.s3 else LocalStorage(args.root)


def new_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:8]


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def print_result(label: str, result: dict[str, Any], args: argparse.Namespace) -> None:
    print(f"{label}: {result['status']} | run_id={result['run_id']}")
    for entry in result["datasets"]:
        detail = ""
        if entry["status"] == "changed":
            detail = f" ({entry['bytes']} bytes)"
        elif entry["status"] == "failed":
            detail = f" | {entry['error']}"
        print(f"  {entry['dataset_id']}: {entry['status']}{detail}")
    print(f"  manifest: {result['manifest_key']}")
    if args.s3:
        print(f"  destino: s3://{args.bucket}/{args.prefix.strip('/')}")


def exit_code(result: dict[str, Any]) -> int:
    """0 para changed/unchanged; 1 para partial/failed (o comando falha se algum dataset falhou)."""
    return 0 if result["status"] in OK_STATUSES else 1
