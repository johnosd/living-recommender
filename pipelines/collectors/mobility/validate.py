"""Validação da resposta de uma matriz 1x1 antes de virar estado (spec 009, FR-016, research R3)."""
import json
import re
from pathlib import Path

DURATION = re.compile(r"\d+(\.\d+)?s")
CONDITIONS = ("ROUTE_EXISTS", "ROUTE_NOT_FOUND")


def validate_routes_response(item: dict, path: Path) -> None:
    """Aceita rota ou `ROUTE_NOT_FOUND`; erro dentro de HTTP 200, corpo malformado ou campo ausente → `ValueError`."""
    text = Path(path).read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("resposta vazia")
    try:
        document = json.loads(text)
    except ValueError as exc:
        raise ValueError("resposta não é JSON") from exc
    if not isinstance(document, list) or len(document) != 1 or not isinstance(document[0], dict):
        raise ValueError("resposta não é uma lista de um elemento")
    element = document[0]
    if element.get("originIndex", 0) != 0 or element.get("destinationIndex", 0) != 0:
        raise ValueError("índices do elemento diferentes de 0/0")
    status = element.get("status")
    code = status.get("code", 0) if isinstance(status, dict) else status  # gRPC OK (0) pode vir omitido ou explícito
    if code not in (None, 0, {}):
        message = str(status.get("message", ""))[:120] if isinstance(status, dict) else ""
        raise ValueError(f"erro no elemento (status {code}): {message}")
    condition = element.get("condition")
    if condition not in CONDITIONS:
        raise ValueError(f"condition inesperada: {condition!r}")
    if condition == "ROUTE_NOT_FOUND":
        return
    distance, duration = element.get("distanceMeters"), element.get("duration")
    if type(distance) is not int or distance < 0:
        raise ValueError(f"distanceMeters ausente ou inválido: {distance!r}")
    if not isinstance(duration, str) or not DURATION.fullmatch(duration):
        raise ValueError(f"duration ausente ou inválida: {duration!r}")
