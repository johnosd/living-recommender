"""Validação da resposta JSON da API de indicadores do INE."""

import json
from pathlib import Path
from typing import Any

MUNICIPAL_CODE_LENGTH = 7  # os 4 últimos caracteres são o `dico`


class IneSchemaError(ValueError):
    """A resposta do INE não tem a estrutura esperada."""


def load_ine_document(path: Path) -> dict[str, Any]:
    """O objeto único dentro da lista que a API devolve."""
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise IneSchemaError("a resposta não é UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise IneSchemaError(f"JSON inválido: {exc.msg}") from exc
    if isinstance(document, list):
        document = document[0] if document else None
    if not isinstance(document, dict):
        raise IneSchemaError("resposta sem objeto de indicador")
    return document


def validate_ine_response(dataset: dict[str, Any], path: Path) -> None:
    """Reprova erro da API, indicador trocado, dados vazios e ausência de códigos municipais."""
    name = dataset["id"]
    document = load_ine_document(path)
    success = document.get("Sucesso") or {}
    if not success.get("Verdadeiro"):
        reason = (success.get("Falso") or [{}])[0].get("Msg") if success.get("Falso") else "sem sucesso"
        raise IneSchemaError(f"{name}: a API informou erro: {reason}")
    if document.get("IndicadorCod") != dataset["indicator"]:
        raise IneSchemaError(
            f"{name}: indicador {document.get('IndicadorCod')!r} no lugar de {dataset['indicator']!r}"
        )
    data = document.get("Dados")
    if not isinstance(data, dict) or not any(data.values()):
        raise IneSchemaError(f"{name}: resposta sem dados")
    if not any(
        len(str(item.get("geocod", ""))) == MUNICIPAL_CODE_LENGTH for rows in data.values() for item in rows
    ):
        raise IneSchemaError(f"{name}: nenhum código geográfico municipal na resposta")
