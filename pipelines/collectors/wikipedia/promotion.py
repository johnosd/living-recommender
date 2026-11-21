"""Transação recuperável limitada aos seis diretórios de saída Wikipedia."""

import json
import os
import shutil
from pathlib import Path

from pipelines.collectors.wikipedia.local import confined, file_hash
from pipelines.collectors.wikipedia.manifest import encode, validate_run_id
from pipelines.collectors.wikipedia.prepare import TABLES

PROMOTED = tuple(f"lake/{layer}/{table}" for table, layer in TABLES.items()) + ("lake/silver/wikipedia_reports",)
JOURNAL = ".build/wikipedia/journal.json"


def tree_hash(path):
    path = Path(path)
    return {p.relative_to(path).as_posix(): file_hash(confined(path, p.relative_to(path)))
            for p in sorted(path.rglob("*")) if p.is_file()}


def output_hashes(root):
    return {relative: tree_hash(confined(root, relative)) for relative in PROMOTED}


def atomic_json(path, document):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".next")
    with temporary.open("wb") as stream:
        stream.write(encode(document))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _load(root):
    path = confined(root, JOURNAL)
    if not path.exists():
        return None
    journal = json.loads(path.read_bytes())
    build_id = validate_run_id(journal["build_id"])
    expected_candidate = f".build/wikipedia/{build_id}"
    if (journal.get("candidate") != expected_candidate or journal.get("schema_version") != 1
            or [e["path"] for e in journal["entries"]] != list(PROMOTED)
            or journal.get("stage") not in {"prepared", "committed", "rolled_back"}):
        raise ValueError("journal inválido; inspecionar antes de recuperar")
    confined(root, expected_candidate)
    for index, entry in enumerate(journal["entries"]):
        if entry["backup"] != f"{expected_candidate}/backups/{index}":
            raise ValueError("backup fora do candidato")
        confined(root, entry["path"])
        confined(root, entry["backup"])
    return journal


def _cleanup_backups(root, journal):
    for entry in journal["entries"]:
        backup = confined(root, entry["backup"])
        if backup.exists():
            if tree_hash(backup) != entry["before"]:
                raise ValueError("backup divergente; não apagar")
            shutil.rmtree(backup)


def recover(root):
    journal = _load(root)
    if journal is None:
        return None
    if journal["stage"] == "committed":
        for entry in journal["entries"]:
            destination = confined(root, entry["path"])
            if not destination.is_dir() or tree_hash(destination) != entry["after"]:
                raise ValueError("commit divergente dos hashes registrados")
        _cleanup_backups(root, journal)
        return "committed"
    if journal["stage"] == "rolled_back":
        return "rolled_back"
    # Inspecionar TODOS os destinos antes de qualquer remoção/restauração.
    for entry in journal["entries"]:
        destination, backup = confined(root, entry["path"]), confined(root, entry["backup"])
        if backup.exists():
            if tree_hash(backup) != entry["before"]:
                raise ValueError("backup corrompido; recuperação exige inspeção")
            if destination.exists() and tree_hash(destination) != entry["after"]:
                raise ValueError("destino alterado fora da transação")
        elif entry["existed"]:
            if not destination.exists() or tree_hash(destination) != entry["before"]:
                raise ValueError("origem anterior não está no destino nem backup")
        elif destination.exists() and tree_hash(destination) != entry["after"]:
            raise ValueError("novo destino desconhecido")
    for entry in reversed(journal["entries"]):
        destination, backup = confined(root, entry["path"]), confined(root, entry["backup"])
        if backup.exists():
            if destination.exists():
                shutil.rmtree(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(backup, destination)
        elif not entry["existed"] and destination.exists():
            shutil.rmtree(destination)
    journal["stage"] = "rolled_back"
    atomic_json(confined(root, JOURNAL), journal)
    return "rolled_back"


def promote(root, candidate, *, check_dependencies, after_move=None):
    root, candidate = Path(root).resolve(), Path(candidate).resolve()
    build_id = validate_run_id(candidate.name)
    if candidate != confined(root, f".build/wikipedia/{build_id}"):
        raise ValueError("candidato fora do diretório de build Wikipedia")
    recover(root)
    entries = []
    for index, relative in enumerate(PROMOTED):
        destination, incoming = confined(root, relative), confined(candidate, relative)
        if not incoming.is_dir() or not tree_hash(incoming):
            raise ValueError("candidato incompleto")
        entries.append({"path": relative, "existed": destination.exists(), "before": tree_hash(destination),
                        "after": tree_hash(incoming), "backup": f".build/wikipedia/{build_id}/backups/{index}"})
    journal = {"schema_version": 1, "build_id": build_id, "candidate": f".build/wikipedia/{build_id}",
               "stage": "prepared", "entries": entries}
    atomic_json(confined(root, JOURNAL), journal)
    try:
        for index, entry in enumerate(entries):
            if not check_dependencies():
                raise ValueError("dependências alteradas antes da promoção")
            destination, incoming, backup = (confined(root, entry["path"]), confined(candidate, entry["path"]),
                                             confined(root, entry["backup"]))
            backup.parent.mkdir(parents=True, exist_ok=True)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                os.replace(destination, backup)
            os.replace(incoming, destination)
            if after_move is not None:
                after_move(index)
        if not check_dependencies() or any(tree_hash(confined(root, e["path"])) != e["after"] for e in entries):
            raise ValueError("dependências/saídas divergentes antes do commit")
        journal["stage"] = "committed"
        atomic_json(confined(root, JOURNAL), journal)
    except (OSError, ValueError, RuntimeError):
        recover(root)
        raise
    try:
        _cleanup_backups(root, journal)
    except (OSError, ValueError) as error:
        return f"commit verificado; limpeza pendente: {error}"
    return None
