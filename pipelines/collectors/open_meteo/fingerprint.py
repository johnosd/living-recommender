"""Identidade do JSON sem o tempo volátil de geração."""
import hashlib
import json
from pathlib import Path


def fingerprint_open_meteo_response(path: Path) -> str:
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc.pop("generationtime_ms", None)
    canonical = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
