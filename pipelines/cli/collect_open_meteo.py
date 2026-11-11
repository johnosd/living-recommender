"""CLI de coleta do clima diário municipal."""
import argparse
import sys
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


def main(argv=None, *, fetcher=None, validator=None, storage=None):
    parser = argparse.ArgumentParser(description="Coleta o clima diário dos municípios pelo Open-Meteo.")
    add_destination_arguments(parser)
    parser.add_argument("--silver", type=Path)
    parser.add_argument("--recollect", action="store_true")
    parser.add_argument('--max-municipalities', type=int)
    parser.add_argument('--no-wait', action='store_true')
    args = parser.parse_args(argv)
    check_destination_arguments(parser, args)
    run_id = new_run_id()
    try:
        catalog = load_catalog(args.catalog) if args.catalog else load_catalog()
        source = get_climate_source(catalog)
        towns = load_climate_municipalities(args.silver or args.root / "lake/silver")
        result = collect_open_meteo(
            catalog, municipalities=towns, storage=storage if storage is not None else make_storage(args),
            fetcher=fetcher if fetcher is not None else make_open_meteo_fetcher(source, wait_on_limits=not args.no_wait),
            validator=validator,
            run_id=run_id, collected_at_utc=utc_now(), work_dir=args.root / ".work/open_meteo" / run_id,
            recollect=args.recollect, max_municipalities=args.max_municipalities,
        )
    except (OSError, ValueError, DatasetCollectionError) as exc:
        print(f"Open-Meteo: falha: {exc}", file=sys.stderr)
        return 1
    if result["up_to_date"]:
        print(f"Open-Meteo: nada a coletar ({result['skipped_current']}/{len(towns)} atuais)")
        return 0
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
    return 1 if counts['failed'] else (2 if counts['pending'] else 0)


if __name__ == "__main__":
    raise SystemExit(main())
