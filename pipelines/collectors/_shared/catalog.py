"""Catálogo versionado de fontes permitidas para coleta."""

from pathlib import Path
from urllib.parse import urlparse

import yaml

REGIONS = ("continente", "acores", "madeira")
DEFAULT_CATALOG = Path(__file__).resolve().parents[3] / "config" / "sources.yml"
REQUIRED_FIELDS = (
    "id",
    "publisher",
    "responsible_party",
    "license_id",
    "collection_method",
    "frequency",
    "territorial_level",
    "version",
    "reference_period",
    "urls",
)


class CatalogError(ValueError):
    """Fonte ausente ou incompleta no catálogo."""


def validate_source(source_id: str, source: dict, *, strict_metadata: bool = True) -> dict:
    """Valida a configuração antes de qualquer acesso à rede."""
    if not isinstance(source, dict):
        raise CatalogError(f"fonte {source_id!r} inválida")
    fields = REQUIRED_FIELDS if strict_metadata else (
        "version", "reference_period", "license_id", "collection_method", "urls"
    )
    missing = [field for field in fields if not source.get(field)]
    if missing:
        raise CatalogError(f"fonte {source_id!r} sem campos: {', '.join(missing)}")
    if source.get("id", source_id) != source_id:
        raise CatalogError(f"identificador divergente para {source_id!r}")
    if source["collection_method"] != "http_download":
        raise CatalogError(f"método não suportado para {source_id!r}")
    urls = source["urls"]
    if not isinstance(urls, dict) or set(urls) != set(REGIONS):
        raise CatalogError("CAOP exige URLs de continente, acores e madeira")
    for region, url in urls.items():
        if not isinstance(url, str) or urlparse(url).scheme != "https" or not urlparse(url).netloc:
            raise CatalogError(f"URL HTTPS inválida para {region}")
    return {"id": source_id, **source}


def get_source(catalog: dict, source_id: str = "caop", *, strict_metadata: bool = True) -> dict:
    """Recusa qualquer fonte não cadastrada."""
    sources = catalog.get("sources", catalog) if isinstance(catalog, dict) else {}
    if not isinstance(sources, dict) or source_id not in sources:
        raise CatalogError(f"fonte não cadastrada: {source_id}")
    return validate_source(source_id, sources[source_id], strict_metadata=strict_metadata)


def load_catalog(path: str | Path = DEFAULT_CATALOG) -> dict:
    """Lê YAML seguro e valida todas as fontes cadastradas."""
    with Path(path).open(encoding="utf-8") as stream:
        catalog = yaml.safe_load(stream)
    if not isinstance(catalog, dict) or not isinstance(catalog.get("sources"), dict):
        raise CatalogError("catálogo deve conter o mapa sources")
    for source_id in catalog["sources"]:
        get_source(catalog, source_id)
    return catalog
