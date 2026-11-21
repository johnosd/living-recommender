"""Catálogo da fonte `google_distances` (spec 009, data-model.md §1): validado antes de qualquer rede."""
from copy import deepcopy
from datetime import date, datetime
from math import isfinite
from urllib.parse import urlsplit

from pipelines.collectors._shared.catalog import CatalogError

SOURCE_ID = "google_distances"
FIELD_MASK = "originIndex,destinationIndex,status,condition,distanceMeters,duration"
REQUIRED_FIELDS = (
    "publisher", "responsible_party", "license_id", "usage_restriction", "attribution", "risk_accepted",
    "substitution", "collection_method", "frequency", "territorial_level", "api_url", "key_env",
    "reference_period", "limits", "max_elements_per_run", "pricing", "modes",
)
TRAVEL_MODES = {"driving": "DRIVE", "transit": "TRANSIT"}


def _positive(value, name: str, *, integer: bool = False) -> None:
    kind = int if integer else (int, float)
    if type(value) is bool or not isinstance(value, kind) or not isfinite(value) or value <= 0:
        raise CatalogError(f"{SOURCE_ID}: {name} precisa ser um número positivo")


def parse_departure(value: str) -> datetime:
    """RFC 3339 com fuso; a falta de fuso é erro porque o dia útil depende do fuso de Lisboa."""
    try:
        parsed = datetime.fromisoformat(value)
    except (ValueError, AttributeError) as exc:
        raise CatalogError(f"{SOURCE_ID}: departure_time inválido: {value!r}") from exc
    if parsed.tzinfo is None:
        raise CatalogError(f"{SOURCE_ID}: departure_time precisa de fuso horário")
    return parsed


def mobility_source(catalog: dict, source_id: str = SOURCE_ID) -> dict:
    """Valida a entrada do catálogo e devolve uma cópia; `CatalogError` antes de qualquer rede."""
    sources = catalog.get("sources", catalog) if isinstance(catalog, dict) else {}
    if not isinstance(sources, dict) or source_id not in sources:
        raise CatalogError(f"fonte não cadastrada: {source_id}")
    source = deepcopy(sources[source_id])
    if not isinstance(source, dict):
        raise CatalogError(f"fonte {source_id!r} inválida")
    missing = [field for field in REQUIRED_FIELDS if not source.get(field)]
    if missing:
        raise CatalogError(f"fonte {source_id!r} sem campos: {', '.join(missing)}")
    if source.get("id", source_id) != source_id or source["collection_method"] != "api_json":
        raise CatalogError(f"{source_id}: identificador ou método inválido")
    if "window" in source or "datasets" in source:
        raise CatalogError(f"{source_id}: window e datasets não se aplicam a esta fonte")
    url = urlsplit(str(source["api_url"]))
    if url.scheme != "https" or not url.netloc:
        raise CatalogError(f"{source_id}: api_url precisa ser HTTPS")
    limits = source["limits"]
    if not isinstance(limits, dict):
        raise CatalogError(f"{source_id}: limits inválido")
    _positive(limits.get("min_interval_seconds"), "limits.min_interval_seconds")
    _positive(limits.get("max_attempts"), "limits.max_attempts", integer=True)
    _positive(source["max_elements_per_run"], "max_elements_per_run", integer=True)
    verified = source.get("pricing_verified_on")
    if verified is not None:
        try:
            date.fromisoformat(str(verified))
        except ValueError as exc:
            raise CatalogError(f"{source_id}: pricing_verified_on precisa ser uma data ISO ou null") from exc
    modes = source["modes"]
    if not isinstance(modes, dict) or not modes:
        raise CatalogError(f"{source_id}: modes precisa ter pelo menos um modo")
    pricing = source["pricing"]
    if not isinstance(pricing, dict):
        raise CatalogError(f"{source_id}: pricing inválido")
    for mode, config in modes.items():
        if mode not in TRAVEL_MODES:
            raise CatalogError(f"{source_id}: modo desconhecido: {mode}")
        if not isinstance(config, dict) or config.get("travel_mode") != TRAVEL_MODES[mode]:
            raise CatalogError(f"{source_id}: {mode} exige travel_mode {TRAVEL_MODES[mode]}")
        if mode == "transit":
            departure = parse_departure(str(config.get("departure_time", "")))
            if departure.weekday() >= 5:
                raise CatalogError(f"{source_id}: departure_time do transit precisa ser um dia útil")
        price = pricing.get(mode)
        if not isinstance(price, dict):
            raise CatalogError(f"{source_id}: pricing sem o modo {mode}")
        for field in ("usd_per_1000", "free_monthly"):
            value = price.get(field)
            if type(value) is bool or not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
                raise CatalogError(f"{source_id}: pricing.{mode}.{field} precisa ser um número maior ou igual a zero")
    return {"id": source_id, **source}
