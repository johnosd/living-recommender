"""Coleta Wikipedia local; pronta para agendamento externo futuro."""

import argparse
import json
import signal
from collections import Counter
from pathlib import Path
from threading import Event, current_thread, main_thread

import pandas as pd
import yaml

from pipelines.cli._common import new_run_id, utc_now
from pipelines.collectors._shared.storage import LocalStorage
from pipelines.collectors.wikipedia.catalog import wikipedia_source
from pipelines.collectors.wikipedia.fetch import WikipediaFetcher
from pipelines.collectors.wikipedia.handler import collect_wikipedia
from pipelines.collectors.wikipedia.identity import (
    load_associations,
    validate_associations,
)
from pipelines.collectors.wikipedia.local import (
    confined,
    dependency_hashes,
    source_lock,
)
from pipelines.collectors.wikipedia.manifest import manifest_key


def main(argv=None, *, fetcher=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--root", type=Path, default=Path(".data"))
    parser.add_argument("--catalog", type=Path, default=Path("config/sources.yml"))
    parser.add_argument("--associations", type=Path, default=Path("config/wikipedia_articles.csv"))
    parser.add_argument("--silver", type=Path)
    parser.add_argument("--contact")
    batch = parser.add_mutually_exclusive_group()
    batch.add_argument("--max-municipalities", type=int)
    batch.add_argument("--resume-run-id")
    args = parser.parse_args(argv)
    run_id, fetch = new_run_id(), None
    interrupted, previous_signal = Event(), None
    try:
        root = args.root.resolve()
        for relative in ("raw/source=wikipedia", "manifests/wikipedia", "reports/wikipedia", ".work/wikipedia"):
            confined(root, relative)
        with source_lock(root):
            silver = args.silver or root / "lake/silver"
            dimension = silver / "dim_municipality/data.parquet"
            paths = [args.catalog, args.associations, dimension]
            before = dependency_hashes(paths)
            catalog = yaml.safe_load(args.catalog.read_text(encoding="utf-8"))
            if args.contact:
                catalog["sources"]["wikipedia"]["contact"] = args.contact
            source = wikipedia_source(catalog)
            associations = load_associations(args.associations)
            municipalities = pd.read_parquet(dimension)[["dico", "official_name", "caop_version"]].to_dict("records")
            validate_associations(municipalities, associations, source["expected_municipalities"])
            storage = LocalStorage(root)
            resume = json.loads(storage.get(manifest_key(args.resume_run_id))) if args.resume_run_id else None
            if current_thread() is main_thread():
                previous_signal = signal.signal(signal.SIGINT, lambda *_: interrupted.set())
            fetch = fetcher or WikipediaFetcher(source, cancelled=interrupted.is_set)
            result = collect_wikipedia(catalog, municipalities=municipalities, associations=associations,
                territory_hash=before[str(dimension.resolve())], storage=storage, fetcher=fetch,
                run_id=run_id, collected_at_utc=utc_now(), work_dir=root / ".work/wikipedia" / run_id,
                resume_manifest=resume, max_municipalities=args.max_municipalities,
                context_checker=lambda: dependency_hashes(paths) == before,
                should_stop=interrupted.is_set, now_utc=utc_now)
            print(json.dumps({"status": result["status"], "run_id": run_id,
                "cycle_id": result["cycle_id"], "manifest": result["manifest_key"],
                "counts": dict(Counter(e["status"] for e in result["entries"])),
                "errors": [{"dico": e["dico"], "error": e["error"], "retry_at": e.get("retry_at")}
                           for e in result["entries"] if e.get("error")]}, ensure_ascii=False))
            if result.get("input_errors") or any(e["status"] == "failed" for e in result["entries"]):
                return 1
            return 2 if any(e["status"] == "pending" for e in result["entries"]) else 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"status": "failed", "run_id": run_id, "error": str(error)}, ensure_ascii=False))
        return 1
    finally:
        if previous_signal is not None:
            signal.signal(signal.SIGINT, previous_signal)
        if fetch is not None and fetcher is None:
            fetch.close()


if __name__ == "__main__":
    raise SystemExit(main())
