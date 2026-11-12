"""CLI de coleta do clima diário municipal."""
import argparse
import sys
import time
from copy import deepcopy
from pathlib import Path

from pipelines.cli._common import (
    add_destination_arguments,
    check_destination_arguments,
    make_storage,
    new_run_id,
    print_result,
    utc_now,
)
from pipelines.collectors._shared.catalog import get_climate_source, load_catalog
from pipelines.collectors._shared.datasets import DatasetCollectionError
from pipelines.collectors.open_meteo.fetch import make_open_meteo_fetcher
from pipelines.collectors.open_meteo.handler import collect_open_meteo
from pipelines.collectors.open_meteo.municipalities import load_climate_municipalities


def main(argv=None, *, fetcher=None, validator=None, storage=None, sleep=time.sleep):
    parser = argparse.ArgumentParser(description="Coleta o clima diário dos municípios pelo Open-Meteo.")
    add_destination_arguments(parser)
    parser.add_argument("--silver", type=Path)
    parser.add_argument("--recollect", action="store_true")
    parser.add_argument('--max-municipalities', type=int)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--no-wait', action='store_true')
    mode.add_argument('--continuous', action='store_true',
                      help='Aguarda cotas e repete falhas temporárias, com checkpoints a cada 10 municípios.')
    args = parser.parse_args(argv)
    check_destination_arguments(parser, args)
    if args.continuous and (args.recollect or args.max_municipalities is not None):
        parser.error('--continuous não combina com --recollect ou --max-municipalities')
    try:
        catalog = deepcopy(load_catalog(args.catalog) if args.catalog else load_catalog())
    except (OSError, ValueError) as exc:
        print(f"Open-Meteo: falha: {exc}", file=sys.stderr)
        return 1
    delays, fetcher_cache = [], [fetcher]
    while True:
        delays.clear()
        code, result = _collect_once(args, catalog=catalog, fetcher_cache=fetcher_cache,
                                     validator=validator, storage=storage,
                                     on_quota=delays.append)
        if (not args.continuous or code == 1 or result is None or result['interrupted']
                or result['up_to_date'] or (code == 0 and not result['remaining'])):
            return code
        if code == 2:
            delay = delays[-1] if delays else 3605
            print(f'  Checkpoint salvo. Retomada automática em {delay:.1f} segundos.', flush=True)
            try:
                while delay > 0:
                    step = min(delay, 60)
                    sleep(step)
                    delay -= step
            except KeyboardInterrupt:
                return 2


def _collect_once(args, *, catalog, fetcher_cache, validator=None, storage=None, on_quota=None):
    run_id = new_run_id()
    try:
        source = get_climate_source(catalog)
        if fetcher_cache[0] is None:
            fetcher_cache[0] = make_open_meteo_fetcher(
                source, wait_on_limits=not (args.no_wait or args.continuous),
                max_attempts=None if args.continuous else 3, on_quota=on_quota)
        towns = load_climate_municipalities(args.silver or args.root / "lake/silver")
        result = collect_open_meteo(
            catalog, municipalities=towns, storage=storage if storage is not None else make_storage(args),
            fetcher=fetcher_cache[0],
            validator=validator,
            run_id=run_id, collected_at_utc=utc_now(), work_dir=args.root / ".work/open_meteo" / run_id,
            recollect=args.recollect, max_municipalities=10 if args.continuous else args.max_municipalities,
        )
    except (OSError, ValueError, DatasetCollectionError) as exc:
        print(f"Open-Meteo: falha: {exc}", file=sys.stderr)
        return 1, None
    if result["up_to_date"]:
        print(f"Open-Meteo: nada a coletar ({result['skipped_current']}/{len(towns)} atuais)")
        return 0, result
    print_result("Open-Meteo", result, args)
    counts = {status: sum(e['status'] == status for e in result['datasets'])
              for status in ('changed', 'unchanged', 'failed', 'pending')}
    print(f"  janela {source['window']['start']}/{source['window']['end']} | modelo {source['model']}")
    print(f"  gravados: {counts['changed']} | inalterados: {counts['unchanged']} | "
          f"falhas: {counts['failed']} | pendentes: {counts['pending']}")
    print(f"  já atuais (sem chamada): {result['skipped_current']} | "
          f"restantes: {counts['pending'] + result['remaining']}")
    for entry in result['datasets']:
        if entry['status'] == 'pending':
            print(f"  {entry['dataset_id']}: pending | {entry['error']}")
    if counts['pending']:
        print('  Continue com o mesmo comando quando a cota estiver disponível; progresso salvo no manifest.')
    return (1 if counts['failed'] else (2 if counts['pending'] else 0)), result


if __name__ == "__main__":
    raise SystemExit(main())
