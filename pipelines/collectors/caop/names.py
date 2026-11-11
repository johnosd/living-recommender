"""Normalização única de nomes territoriais para comparação entre fontes."""

import unicodedata


def normalize_name(value: str) -> str:
    """Retorna nome minúsculo, sem acentos e com espaços internos únicos."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("nome territorial vazio")
    collapsed = " ".join(value.split())
    decomposed = unicodedata.normalize("NFKD", collapsed)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).lower()
