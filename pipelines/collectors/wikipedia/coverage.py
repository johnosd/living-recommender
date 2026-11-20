"""Fronteira pública da prontidão municipal; stub da spec 008."""

from collections import Counter
from typing import Any

from pipelines.collectors.wikipedia.identity import evidence_valid


def assess_wikipedia_coverage(
    municipalities: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    *,
    input_errors: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Retorna ready, blockers, expected_municipalities e counts sem fazer rede.

    entries trazem os estados da última tentativa selecionada; estado anterior
    preservado não transforma falha atual em sucesso.
    """
    expected = [r["dico"] for r in municipalities]
    codes = [r.get("dico") for r in entries]
    blockers = list(input_errors)
    if not expected or len(set(expected)) != len(expected):
        blockers.append("universo municipal vazio/duplicado")
    missing, extra = set(expected) - set(codes), set(codes) - set(expected)
    if missing:
        blockers.append(f"DICO perdidos: {sorted(missing)}")
    if extra:
        blockers.append(f"DICO extras: {sorted(str(c) for c in extra)}")
    if len(set(codes)) != len(codes):
        blockers.append("DICO duplicados")
    for row in entries:
        status = row.get("status")
        if status == "valid":
            if (row.get("identity_validated") is not True or row.get("extraction_complete") is not True
                    or type(row.get("revision_id")) is not int or row["revision_id"] < 1):
                blockers.append(f"{row.get('dico')}: identidade/revisão/extração incompleta")
        elif status == "absent":
            if not row.get("reason") or not evidence_valid(row.get("absence_evidence") or {}):
                blockers.append(f"{row.get('dico')}: ausência sem comprovação")
        else:
            blockers.append(f"{row.get('dico')}: {status or 'estado desconhecido'}")
    return {"ready": not blockers, "blockers": blockers, "expected_municipalities": len(expected),
            "counts": dict(Counter(r.get("status", "unknown") for r in entries))}
