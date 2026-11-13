"""Importação imutável de snapshots mensais do Idealista."""

import hashlib
import json
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from pipelines.collectors._shared.catalog import get_manual_snapshot_source
from pipelines.collectors._shared.manifest import encode_manifest, file_digest
from pipelines.collectors._shared.storage import _canonical_path, validate_key


class IdealistaError(ValueError):
    """Importação ou processamento reprovado sem substituir a base vigente."""


def validate_month(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value) or value[:4] == "0000":
        raise IdealistaError("snapshot_month deve ser YYYY-MM válido")
    return value


def read_rows(path: Path) -> list[dict]:
    """Valida a forma do bruto sem modificar valores ou descartar registros."""
    try:
        rows = json.loads(path.read_text(encoding="utf-8-sig"),
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (UnicodeError, ValueError) as exc:
        raise IdealistaError(f"JSON inválido: {path.name}") from exc
    if not isinstance(rows, list):
        raise IdealistaError(f"JSON deve conter lista: {path.name}")
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise IdealistaError(f"registro não é objeto: {path.name}, linha {index}")
        identity = row.get("id")
        if isinstance(identity, bool) or not isinstance(identity, (str, int)) or not str(identity).strip():
            raise IdealistaError(f"ID ausente ou inválido: {path.name}, linha {index}")
        for key, types in (("Titulo", (str,)), ("Preco", (str, int, float)),
                           ("tipologia", (str,)), ("areaBrutaM2", (str, int, float))):
            if key not in row or (row[key] is not None and (isinstance(row[key], bool) or not isinstance(row[key], types))):
                raise IdealistaError(f"campo {key} ausente ou tipo inválido: {path.name}, linha {index}")
    return rows


def snapshot_fingerprint(entries: list[dict]) -> str:
    files = sorted(entries, key=lambda entry: entry["relative_path"])
    return hashlib.sha256(encode_manifest(
        [{k: entry[k] for k in ("relative_path", "sha256", "bytes")} for entry in files]
    )).hexdigest()


def validate_snapshot_manifest(manifest: dict) -> None:
    """Confere consistência do inventário inteiro, inclusive remoção ou repetição de arquivos."""
    try:
        if manifest["schema_version"] != 1 or manifest["source_id"] != "idealista" or manifest["status"] != "changed":
            raise ValueError("tipo/versão inválidos")
        month = validate_month(manifest["snapshot_month"])
        run = manifest["run_id"]
        if not isinstance(run, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", run):
            raise ValueError("run inválido")
        timestamp = datetime.fromisoformat(manifest["imported_at_utc"])
        if timestamp.tzinfo is None or timestamp.utcoffset() != timedelta(0):
            raise ValueError("horário sem UTC")
        if manifest["reference_period"] != month or manifest["source_run_id"] != run:
            raise ValueError("período/run divergente")
        files = manifest["files"]
        if not isinstance(files, list) or not files:
            raise ValueError("inventário vazio")
        paths = set()
        for entry in files:
            relative = validate_key(entry["relative_path"])
            if relative in paths or not relative.lower().endswith(".json"):
                raise ValueError("caminho duplicado/inválido")
            paths.add(relative)
            if entry["key"] != f"raw/source=idealista/snapshot={month}/run_id={run}/{relative}":
                raise ValueError("chave fora do snapshot")
            if not isinstance(entry["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]):
                raise ValueError("hash inválido")
            if type(entry["bytes"]) is not int or entry["bytes"] <= 0:
                raise ValueError("tamanho inválido")
            if type(entry["records"]) is not int or entry["records"] < 0:
                raise ValueError("contagem inválida")
        if (type(manifest["records"]) is not int or manifest["records"] != sum(entry["records"] for entry in files)
                or snapshot_fingerprint(files) != manifest["snapshot_sha256"]):
            raise ValueError("inventário/total/fingerprint divergente")
    except (KeyError, TypeError, ValueError) as exc:
        raise IdealistaError(f"manifest Idealista inválido: {exc}") from exc


def latest_snapshot(storage, snapshot_month: str) -> dict | None:
    validate_month(snapshot_month)
    candidates = []
    for key in sorted(storage.list_keys("manifests/idealista/")):
        if not key.endswith(".json"):
            continue
        try:
            manifest = json.loads(storage.get(key))
        except (ValueError, UnicodeError) as exc:
            raise IdealistaError(f"manifest Idealista inválido: {key}") from exc
        if not isinstance(manifest, dict):
            raise IdealistaError(f"manifest Idealista não é objeto: {key}")
        if (manifest.get("source_id") == "idealista" and manifest.get("status") == "changed"
                and manifest.get("snapshot_month") == snapshot_month):
            validate_snapshot_manifest(manifest)
            candidates.append(manifest)
    return max(candidates, key=lambda m: (datetime.fromisoformat(m["imported_at_utc"]), m["run_id"])) if candidates else None


def check_local_paths(directory: Path, root: Path) -> None:
    """Rejeita sobreposição antes de criar storage, candidato ou manifest de erro."""
    target = _canonical_path(Path(root).resolve())
    origin = _canonical_path(Path(directory).resolve())
    if target == origin or target.is_relative_to(origin) or origin.is_relative_to(target):
        raise IdealistaError("origem e destino não podem se sobrepor")


def import_snapshot(catalog, *, storage, directory, snapshot_month, run_id, imported_at_utc):
    """Valida cópias privadas antes de gravar; manifest changed é o commit do lote."""
    validate_month(snapshot_month)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id or ""):
        raise IdealistaError("run_id inválido")
    timestamp = datetime.fromisoformat(imported_at_utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() != timedelta(0):
        raise IdealistaError("imported_at_utc deve estar em UTC")
    source = get_manual_snapshot_source(catalog)
    directory = Path(directory)
    if hasattr(storage, "root"):
        check_local_paths(directory, storage.root)
    manifest_key = f"manifests/idealista/{run_id}.json"
    if manifest_key in storage.list_keys("manifests/idealista/"):
        raise IdealistaError("run_id já usado; informe outro run")
    manifest = {"schema_version": 1, "source_id": "idealista", "run_id": run_id,
                "source_run_id": run_id, "snapshot_month": snapshot_month,
                "reference_period": snapshot_month, "collected_at_utc": None,
                "imported_at_utc": imported_at_utc, "source_directory": str(directory.resolve()),
                "status": "failed", "files": [], "records": 0, "error": None,
                **{k: source[k] for k in ("publisher", "responsible_party", "collection_method", "license_id",
                                          "attribution", "usage_restriction")}}
    try:
        if directory.is_symlink() or directory.is_junction() or not directory.is_dir():
            raise IdealistaError("pasta de extração ausente ou symlink")
        paths = sorted(directory.rglob("*"), key=lambda p: p.relative_to(directory).as_posix())
        if any(path.is_symlink() or path.is_junction() for path in paths):
            raise IdealistaError("symlinks/junctions não são permitidos na extração")
        files = [path for path in paths if path.is_file() and path.suffix.lower() == ".json"]
        if not files:
            raise IdealistaError("pasta sem arquivos JSON")
        with TemporaryDirectory(prefix="idealista-import-") as temp:
            staged, entries = [], []
            for index, path in enumerate(files):
                relative = validate_key(path.relative_to(directory).as_posix())
                copied = Path(temp) / f"{index}.json"
                shutil.copyfile(path, copied)
                rows = read_rows(copied)
                key = f"raw/source=idealista/snapshot={snapshot_month}/run_id={run_id}/{relative}"
                digest = file_digest(copied, key=key, region=relative)
                entries.append({"relative_path": relative, "key": key, "sha256": digest["sha256"],
                                "bytes": digest["bytes"], "records": len(rows)})
                staged.append(copied)
            fingerprint = snapshot_fingerprint(entries)
            manifest.update(files=entries, snapshot_sha256=fingerprint,
                            records=sum(entry["records"] for entry in entries))
            previous = latest_snapshot(storage, snapshot_month)
            if previous and fingerprint == previous["snapshot_sha256"]:
                manifest.update(status="unchanged", source_run_id=previous["run_id"], files=previous["files"])
            else:
                for entry, copied in zip(entries, staged, strict=True):
                    storage.put_file(entry["key"], copied)
                manifest["status"] = "changed"
            storage.put(manifest_key, encode_manifest(manifest))
    except (OSError, ValueError) as exc:
        manifest.update(status="failed", error=str(exc))
        # Arquivos raw órfãos de falha de escrita não são vigentes sem manifest changed.
        if manifest_key not in storage.list_keys("manifests/idealista/"):
            storage.put(manifest_key, encode_manifest(manifest))
        raise IdealistaError(str(exc)) from exc
    return {**manifest, "manifest_key": manifest_key}
