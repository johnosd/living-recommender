"""Valida a resposta diária antes de aceitar um estado municipal."""
import json
import math
from datetime import date, timedelta
from pathlib import Path


def validate_open_meteo_response(item: dict, path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ValueError("resposta vazia")
    try:
        doc = json.loads(text)
    except ValueError as exc:
        raise ValueError("resposta não é um objeto JSON") from exc
    if not isinstance(doc, dict):
        raise ValueError("resposta não é um objeto JSON")  # noqa: TRY004 - formato externo inválido
    if doc.get("error"):
        raise ValueError(f"API devolveu erro: {doc.get('reason', 'desconhecido')}")
    daily, units = doc.get("daily"), doc.get("daily_units")
    if not isinstance(daily, dict):
        raise ValueError("resposta sem daily")  # noqa: TRY004 - formato externo inválido
    if not isinstance(units, dict):
        raise ValueError("resposta sem daily_units")  # noqa: TRY004 - formato externo inválido
    start, end = (date.fromisoformat(item["window"][k]) for k in ("start", "end"))
    expected = [(start + timedelta(days=n)).isoformat() for n in range((end-start).days+1)]
    times = daily.get("time")
    if times != expected:
        received = times if isinstance(times, list) else []
        raise ValueError(f"dias: esperados {len(expected)} ({start}..{end}), recebidos "
                         f"{len(received)} ({received[:1]}..{received[-1:]})")
    for variable in item["variables"]:
        name, unit = variable["id"], variable["unit"]
        if name not in daily:
            raise ValueError(f"variável ausente: {name}")
        values = daily[name]
        if not isinstance(values, list) or len(values) != len(times):
            raise ValueError(f"série com tamanho errado: {name}")
        if units.get(name) != unit:
            raise ValueError(f"unidade inesperada em {name}: {units.get(name)} (esperada {unit})")
        for value in values:
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
                raise ValueError(f"valor inválido em {name}: {value}")
        if all(value is None for value in values):
            raise ValueError(f"variável sem nenhum valor: {name}")
    if any(type(doc.get(k)) not in (int, float) or not math.isfinite(doc[k]) for k in ("latitude", "longitude")):
        raise ValueError("resposta sem coordenadas")
    if not isinstance(doc.get("timezone"), str) or not doc["timezone"]:
        raise ValueError("resposta sem timezone")
