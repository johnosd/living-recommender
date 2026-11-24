"""CLI que gera (e, opcionalmente, serve) o site do `dbt docs` local (spec 010, US4; `contracts/cli.md` §3).

Sequência em `logic/site.md`. O site é local: não é publicado, e `--serve` escuta só em 127.0.0.1.
Códigos de saída: 0 ok; 1 manifest inconsistente ou falha do dbt; 2 uso ou `dbt` ausente.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from pipelines.modeldocs.model import ModelError, load_model
from pipelines.modeldocs.site import lake_catalog_json, link_sources_to_models

ROOT = Path(__file__).resolve().parents[2]
DBT_PROJECT = ROOT / "analytics" / "dbt"
DEFAULT_ROOT = ROOT / ".data"
HOST = "127.0.0.1"
DEFAULT_PORT = 8741  # a 8080 costuma estar com Docker/WSL, que respondem em `localhost` (::1) no lugar do dbt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipelines.cli.dbt_docs_site", description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="pasta com `lake/` (opcional)")
    parser.add_argument("--output", type=Path, help="pasta do site (padrão: <root>/dbt-docs)")
    parser.add_argument("--serve", action="store_true", help=f"serve o site em {HOST} depois de gerar")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="porta do `--serve`")
    return parser


def _environment(output: Path) -> dict[str, str]:
    """O dbt abre uma conexão DuckDB mesmo com `--empty-catalog`: aponta para dentro da saída, nunca para `.data/ci`."""
    return {**os.environ, "DBT_TARGET_PATH": str(output), "DBT_LOG_PATH": str(output / "logs"),
            "CAOP_DUCKDB_PATH": str(output / "never-used.duckdb")}


def _dbt(executable: str, *args: str) -> list[str]:
    return [executable, "docs", *args, "--project-dir", str(DBT_PROJECT), "--profiles-dir", str(DBT_PROJECT)]


def port_in_use(port: int) -> bool:
    """Verdadeiro se algo já atende a porta em IPv4 ou IPv6; o navegador resolve `localhost` para `::1` primeiro."""
    for family, address in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        try:
            with socket.socket(family, socket.SOCK_STREAM) as probe:
                probe.settimeout(0.5)
                if probe.connect_ex((address, port)) == 0:
                    return True
        except OSError:
            continue
    return False


def _write_json(path: Path, body: dict) -> None:
    path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")


def generate(root: Path, output: Path, executable: str) -> int:
    """Gera `index.html`, `manifest.json` (com as fontes ligadas aos modelos) e `catalog.json` em `output`."""
    output.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(_dbt(executable, "generate", "--empty-catalog", "--target", "local"),
                            capture_output=True, text=True, env=_environment(output), check=False)
    if result.returncode != 0:
        print(f"`dbt docs generate` falhou (código {result.returncode}):\n{result.stdout[-1500:]}", file=sys.stderr)
        return 1
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    try:
        model = load_model(manifest)
    except ModelError as error:
        print(f"Modelo de dados inconsistente: {error}", file=sys.stderr)
        return 1
    _write_json(output / "manifest.json", link_sources_to_models(manifest))
    empty = json.loads((output / "catalog.json").read_text(encoding="utf-8"))
    _write_json(output / "catalog.json", lake_catalog_json(model, root / "lake", generated_at=datetime.now(UTC),
                                                           base=empty))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Gera o site do dbt docs; nunca escreve em `raw/`, `lake/` nem em `.data/ci`."""
    args = _parser().parse_args(argv)
    output = (args.output or args.root / "dbt-docs").resolve()  # o dbt resolve caminhos relativos a partir do projeto
    executable = shutil.which("dbt")
    if executable is None:
        print("`dbt` não encontrado no PATH; rode com `uv run --locked python -m pipelines.cli.dbt_docs_site`",
              file=sys.stderr)
        return 2
    if args.serve and port_in_use(args.port):
        print(f"A porta {args.port} já está em uso (Docker, WSL ou outro servidor). Use --port com outra porta.",
              file=sys.stderr)
        return 2
    status = generate(args.root.resolve(), output, executable)
    if status != 0:
        return status
    print(f"Site do dbt docs: {output / 'index.html'}")
    if not args.serve:
        return 0
    print(f"Servindo em http://{HOST}:{args.port} (abra exatamente este endereço, não `localhost`; Ctrl+C encerra)")
    try:
        subprocess.run(_dbt(executable, "serve", "--host", HOST, "--port", str(args.port), "--no-browser"),
                       env=_environment(output), check=False)
    except KeyboardInterrupt:
        print("Servidor encerrado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
