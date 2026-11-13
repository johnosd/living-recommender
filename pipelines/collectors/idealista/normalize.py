"""Conversões explícitas de preço, área e tipologia; nunca imputa valores."""

import math
import re


def _positive(value, *, price=False):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip().replace("\xa0", " ")
        suffix = r"\s*(?:€\s*(?:/\s*mês)?)?" if price else r"\s*(?:m²|m2)?"
        match = re.fullmatch(r"(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?)" + suffix, text)
        if not match:
            return None
        value = match[1].replace(".", "").replace(",", ".")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) and result > 0 else None


def normalize_listing(row):
    price = _positive(row.get("Preco"), price=True)
    area = _positive(row.get("areaBrutaM2"))
    match = re.fullmatch(r"T(\d{1,2})", (row.get("tipologia") or "").strip(), flags=re.IGNORECASE)
    bedrooms = int(match[1]) if match else None
    typology = (f"T{bedrooms}" if bedrooms < 4 else "T4+") if bedrooms is not None else None
    flags = []
    for field, value in (("price", price), ("area", area), ("typology", typology)):
        if value is None:
            flags.append(f"missing_or_invalid_{field}")
    return {"asking_rent_eur": price, "area_m2": area, "typology": typology,
            "bedrooms": bedrooms, "quality_flags": "|".join(flags)}
