"""Resolução e redação da chave do Google (spec 009, FR-010, constitution I): o valor nunca é impresso."""
from pathlib import Path
from urllib.parse import quote

REDACTED = "[REDACTED]"
MIN_KEY_LENGTH = 8


def _read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        name, _, value = text.removeprefix("export ").partition("=")
        values[name.strip()] = value.strip().strip("'\"")
    return values


def resolve_api_key(env: dict, source: dict, *, root=None) -> str:
    """Lê a chave de `env` e, só se `root` for dado, do `.env` dessa raiz; falha sem imprimir valor."""
    name = source["key_env"]
    value = (env or {}).get(name)
    if not value and root is not None:
        value = _read_dotenv(Path(root) / ".env").get(name)
    if not value or not value.strip():
        raise ValueError(f"chave ausente: defina {name} no ambiente ou em .env")
    value = value.strip()
    if len(value) < MIN_KEY_LENGTH or any(char.isspace() for char in value):
        raise ValueError(f"{name} parece inválida (curta demais ou com espaços)")
    return value


def redact(text, *secrets: str) -> str:
    """Troca cada segredo, e a sua forma codificada em URL, por `[REDACTED]`."""
    result = str(text)
    for secret in secrets:
        if secret:
            for form in {secret, quote(secret, safe=""), quote(secret)}:
                result = result.replace(form, REDACTED)
    return result
