"""Build local isolado de anúncios manuais do Idealista."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from pipelines.cli._common import utc_now
from pipelines.cli._promote import promote_paths
from pipelines.collectors.idealista.prepare import prepare_snapshot
from pipelines.collectors.idealista.snapshot import IdealistaError

PROMOTED = ("lake/bronze/idealista_occurrences", "lake/silver/idealista_listings", "lake/bronze/idealista_reports")


def _verify_exports(candidate: Path, summary: dict) -> None:
    """Confere arquivos reais, pois a view dbt filtra uma linha nula artificial quando vazia."""
    for relative, prepared, expected in ((PROMOTED[0], "occurrences.parquet", summary["records"]),
                                         (PROMOTED[1], "listings.parquet", summary["unique_listings"])):
        path = candidate / relative / "data.parquet"
        frame = pd.read_parquet(path)
        if expected == 0 and len(frame) == 1 and frame.isna().all().all():
            # dbt-duckdb external.sql insere NULLs para representar schema vazio.
            # Consumidores do lake leem o Parquet, não a view que esconde essa linha.
            shutil.copyfile(candidate / "prepared" / prepared, path)
            frame = pd.read_parquet(path)
        if len(frame) != expected or frame.listing_id.isna().any():
            raise IdealistaError(f"exportação dbt diverge do snapshot: {relative}")


def _run_dbt(candidate: Path, silver: Path) -> None:
    executable = shutil.which("dbt")
    if not executable:
        raise IdealistaError("dbt não encontrado; execute com uv run --locked")
    env = os.environ.copy()
    env.update({"IDEALISTA_BUILD_DIR": candidate.as_posix(),
                "IDEALISTA_PREPARED_DIR": (candidate / "prepared").as_posix(),
                "OBS_SILVER_DIR": silver.as_posix(), "CAOP_DUCKDB_PATH": (candidate / "idealista.duckdb").as_posix()})
    command = [executable, "build", "--project-dir", "analytics/dbt", "--profiles-dir", "analytics/dbt",
               "--target", "local", "--select", "tag:idealista", "--target-path", str(candidate / "dbt-target"),
               "--log-path", str(candidate / "dbt-logs")]
    result = subprocess.run(command, cwd=Path(__file__).resolve().parents[2], env=env,
                            text=True, capture_output=True, check=False)
    if result.returncode:
        detail = "\n".join((result.stdout + "\n" + result.stderr).splitlines()[-30:])
        raise IdealistaError(f"dbt build Idealista falhou ({result.returncode}):\n{detail}")


def build_idealista(root, *, snapshot_month):
    """Prepara e testa em candidato isolado; substitui somente os três diretórios desta feature."""
    root = Path(root).resolve()
    parent = root / ".build" / "idealista"
    parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="build-", dir=parent) as temporary:
        candidate = Path(temporary).resolve()
        summary = prepare_snapshot(root, candidate / "prepared", snapshot_month=snapshot_month, processed_at_utc=utc_now())
        for relative in PROMOTED:
            (candidate / relative).mkdir(parents=True, exist_ok=True)
        _run_dbt(candidate, root / "lake" / "silver")
        _verify_exports(candidate, summary)
        report_dir = candidate / PROMOTED[2]
        for filename in ("summary.json", "coverage.csv", "duplicates.csv"):
            shutil.copyfile(candidate / "prepared" / filename, report_dir / filename)
        shutil.copyfile(candidate / "dbt-target" / "run_results.json", report_dir / "dbt_run_results.json")
        promote_paths(root, candidate, PROMOTED)
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Constrói anúncios únicos e cobertura de um snapshot manual do Idealista.")
    parser.add_argument("--local", action="store_true", help="build local (único nesta fase)")
    parser.add_argument("--root", type=Path, default=Path(".data"))
    parser.add_argument("--snapshot-month", required=True, help="período da extração, YYYY-MM")
    args = parser.parse_args(argv)
    try:
        result = build_idealista(args.root, snapshot_month=args.snapshot_month)
    except (OSError, ValueError, KeyError) as exc:
        print(f"Idealista: falha: {exc}", file=sys.stderr)
        return 1
    print(f"Idealista: período {result['snapshot_month']} | {result['records']} ocorrências | "
          f"{result['unique_listings']} anúncios únicos | {result['duplicate_occurrences']} repetições")
    print(f"  Municípios com amostra: {result['municipalities_with_listings']}/{result['municipalities_expected']}")
    print(f"  Regionais: {result['regional_listings']} | conflitos territoriais: {result['territorial_conflicts']}")
    print(f"  Freguesia resolvida: {result['listings_with_parish']} | municipais sem freguesia: "
          f"{result['municipal_listings_without_parish']}")
    print(f"  Aviso: {result['conflicting_listings']} IDs com campos divergentes; escolha por ordem de arquivo, sem presumir recência.")
    print(f"  Relatórios locais: {args.root / PROMOTED[2]}")
    print("  Dados históricos, não publicados. Horário original da coleta desconhecido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
