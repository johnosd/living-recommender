"""CLI local do cálculo único de tempo e distância de carro (spec 009, contracts/mobility-cli.md).

Por padrão só estima (sem rede e sem chave). Gastar exige `--execute` e a confirmação do número de elementos.
"""
import argparse
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pipelines.cli._common import (
    add_destination_arguments,
    check_destination_arguments,
    make_storage,
    new_run_id,
    utc_now,
)
from pipelines.collectors._shared.catalog import CatalogError, load_catalog
from pipelines.collectors._shared.datasets import DatasetCollectionError
from pipelines.collectors.mobility.catalog import (
    SOURCE_ID,
    mobility_source,
    parse_departure,
)
from pipelines.collectors.mobility.estimate import estimate_run
from pipelines.collectors.mobility.fetch import make_routes_fetcher
from pipelines.collectors.mobility.handler import collect_mobility
from pipelines.collectors.mobility.municipalities import load_mobility_municipalities
from pipelines.collectors.mobility.poles import load_poles
from pipelines.collectors.mobility.secrets import redact, resolve_api_key

ROOT = Path(__file__).resolve().parents[2]
DEPARTURE_WINDOW_DAYS = 90
PRICE_STALE_DAYS = 30


def _print_estimate(source: dict, estimate: dict) -> None:
    modes = ", ".join(f"{mode}={count}" for mode, count in estimate["elements"].items())
    print(f"Mobilidade: estimativa para {SOURCE_ID} ({', '.join(source['modes'])})")
    print(f"  pares esperados: {estimate['pairs_total']} (identidade, sem chamada: {estimate['identity']})")
    print(f"  a consultar: {estimate['new']} novos + {estimate['stale']} desatualizados")
    print(f"  elementos por modo: {modes} | total: {estimate['elements_total']} | teto por execução: {estimate['ceiling']}")
    print(f"  custo estimado: US$ {estimate['cost_usd_estimate']:.2f} (dentro dos tetos gratuitos mensais; "
          f"pior caso sem teto gratuito: US$ {estimate['cost_usd_worst_case']:.2f})")
    print("  Preços e tetos vêm do catálogo e precisam ser conferidos na página oficial do Google; "
          "o teto gratuito é mensal e pode já ter sido usado por outra atividade da conta.")


def _problems(args, source: dict, estimate: dict, env: dict | None) -> tuple[list[str], str | None]:
    """Todas as recusas de uma vez: o operador vê tudo o que falta, sem descobrir uma por tentativa."""
    problems: list[str] = []
    if args.confirm_elements is None:
        problems.append("--execute exige --confirm-elements com o total de elementos da estimativa "
                        f"({estimate['elements_total']})")
    elif args.confirm_elements != estimate["elements_total"]:
        problems.append(f"--confirm-elements {args.confirm_elements} difere da estimativa atual "
                        f"({estimate['elements_total']} elementos)")
    ceiling = args.max_elements if args.max_elements is not None else source["max_elements_per_run"]
    if estimate["elements_total"] > ceiling:
        problems.append(f"{estimate['elements_total']} elementos excedem o teto de {ceiling} por execução "
                        "(eleve com --max-elements, de forma explícita)")
    verified = source.get("pricing_verified_on")
    if verified is None:
        problems.append("pricing_verified_on é nulo: confira os preços na página oficial do Google e preencha a data "
                        "no catálogo")
    elif (datetime.now(UTC).date() - datetime.fromisoformat(str(verified)).date()).days > PRICE_STALE_DAYS:
        print(f"AVISO: os preços foram conferidos em {verified}, há mais de {PRICE_STALE_DAYS} dias.")
    if "transit" in source["modes"]:
        departure = parse_departure(source["modes"]["transit"]["departure_time"])
        now = datetime.now(UTC)
        if not now <= departure <= now + timedelta(days=DEPARTURE_WINDOW_DAYS):
            problems.append("modes.transit.departure_time precisa estar entre agora e "
                            f"{DEPARTURE_WINDOW_DAYS} dias à frente")
    key = None
    try:
        key = resolve_api_key(os.environ if env is None else env, source, root=ROOT if env is None else None)
    except ValueError as exc:
        problems.append(str(exc))
    return problems, key


def main(argv=None, *, client=None, fetcher=None, storage=None, env=None, municipalities=None, poles=None,
         sleep=time.sleep) -> int:
    parser = argparse.ArgumentParser(description="Estima e, com confirmação, calcula o tempo de carro até os polos.")
    add_destination_arguments(parser)
    parser.add_argument("--silver", type=Path, help="Silver da CAOP (padrão: <root>/lake/silver)")
    parser.add_argument("--poles", type=Path, help="catálogo de polos (padrão: config/poles.yml)")
    parser.add_argument("--execute", action="store_true", help="consulta o Google; sem esta opção só estima")
    parser.add_argument("--confirm-elements", type=int, help="total de elementos da estimativa, para confirmar")
    parser.add_argument("--max-elements", type=int, help="eleva o teto por execução do catálogo, de forma explícita")
    args = parser.parse_args(argv)
    check_destination_arguments(parser, args)
    try:
        catalog = load_catalog(args.catalog) if args.catalog else load_catalog()
        source = mobility_source(catalog)
        if municipalities is None:
            municipalities = load_mobility_municipalities(args.silver or args.root / "lake/silver")
        if poles is None:
            poles = load_poles(args.poles or ROOT / "config/poles.yml", municipalities)
        storage = storage if storage is not None else make_storage(args)
        estimate = estimate_run(catalog, municipalities=municipalities, poles=poles, storage=storage)
    except (CatalogError, OSError, ValueError) as exc:
        print(f"Mobilidade: falha: {exc}", file=sys.stderr)
        return 1
    _print_estimate(source, estimate)
    if not args.execute:
        return 0
    problems, key = _problems(args, source, estimate, env)
    if problems:
        for problem in problems:
            print(f"Mobilidade: recusado: {redact(problem, key)}", file=sys.stderr)
        return 1
    if not estimate["elements_total"]:
        print("Mobilidade: nada a coletar (todos os pares estão atuais)")
        return 0
    run_id = new_run_id()
    try:
        fetch = fetcher or make_routes_fetcher(source, api_key=key, client=client, sleep=sleep)
        result = collect_mobility(catalog, municipalities=municipalities, poles=poles, storage=storage, fetcher=fetch,
                                  run_id=run_id, collected_at_utc=utc_now(),
                                  work_dir=args.root / ".work" / SOURCE_ID / run_id,
                                  max_elements=None, redact=lambda text: redact(text, key))
    except (OSError, ValueError, DatasetCollectionError) as exc:
        print(f"Mobilidade: falha: {redact(exc, key)}", file=sys.stderr)
        return 1
    counts = {status: sum(entry["status"] == status for entry in result["datasets"])
              for status in ("changed", "unchanged", "failed", "pending")}
    print(f"Mobilidade: {result['status']} | run_id={run_id}")
    print(f"  gravados: {counts['changed']} | inalterados: {counts['unchanged']} | falhas: {counts['failed']} | "
          f"pendentes: {counts['pending']}")
    for entry in result["datasets"]:
        if entry["status"] in ("failed", "pending"):
            print(f"  {entry['dataset_id']}: {entry['status']} | {redact(entry['error'], key)}")
    if counts["pending"]:
        print("  Continue com o mesmo comando; só os pares pendentes serão consultados.")
    return 1 if counts["failed"] else (2 if counts["pending"] else 0)


if __name__ == "__main__":
    raise SystemExit(main())
