"""CSV sintéticos do Pordata nos três layouts reais observados em 2026-11-11 (research R1).

- ``a``: 9 colunas, `08. Símbolo` antes de `07. Escala` (ex.: tabelas 295, 464, 581).
- ``b``: 10 colunas, com `Nome País (Europa)` (tabelas 1 e 559).
- ``c``: dataset 4, símbolo e valor antes de `Max. 08. Escala `.
"""

from collections.abc import Mapping
from pathlib import Path

HEADERS = {
    "a": [
        ("01. Ano", "Ano"), ("02. Nome Região (Portugal)", "Nome Região (Portugal)"),
        ("03. Âmbito Geográfico", "Âmbito Geográfico"), ("04. Filtro 1", "Filtro 1"),
        ("05. Filtro 2", "Filtro 2"), ("06. Filtro 3", "Filtro 3"), ("08. Símbolo", "Símbolo"),
        ("07. Escala", "Escala"), ("09. Valor", "Valor"),
    ],
    "b": [
        ("01. Ano", "Ano"), ("02. Nome País (Europa)", "Nome País (Europa)"),
        ("03. Nome Região (Portugal)", "Nome Região (Portugal)"),
        ("04. Âmbito Geográfico", "Âmbito Geográfico"), ("05. Filtro 1", "Filtro 1"),
        ("06. Filtro 2", "Filtro 2"), ("07. Filtro 3", "Filtro 3"), ("08. Escala ", "Escala"),
        ("09. Símbolo", "Símbolo"), ("10. Valor", "Valor"),
    ],
    "c": [
        ("01. Ano", "Ano"), ("02. Nome País (Europa)", "Nome País (Europa)"),
        ("03. Nome Região (Portugal)", "Nome Região (Portugal)"),
        ("04. Âmbito Geográfico", "Âmbito Geográfico"), ("05. Filtro 1", "Filtro 1"),
        ("06. Filtro 2", "Filtro 2"), ("07. Filtro 3", "Filtro 3"), ("09. Símbolo", "Símbolo"),
        ("10. Valor", "Valor"), ("Max. 08. Escala ", "Escala"),
    ],
}


def pordata_csv(
    layout: str = "a",
    municipalities: tuple[str, ...] = ("Évora", "Lagoa"),
    years: tuple[int, ...] = (2023, 2024),
    unit: str = " farmácias",
    *,
    filter_1: str = "",
    with_symbols: bool = False,
    value_offset: int = 0,
) -> str:
    """CSV com uma linha de país (layouts b/c), uma de agregação e uma por município e ano.

    Com ``with_symbols``, o primeiro município fica sem valor e com `x` no último ano, e o
    segundo recebe `r` (revisto) com valor.
    """
    header = HEADERS[layout]
    lines = [",".join(raw for raw, _ in header)]

    def row(**fields: str) -> str:
        return ",".join(fields.get(label, "") for _, label in header)

    if layout in ("b", "c"):
        lines.append(row(**{"Ano": "2024", "Nome País (Europa)": "Alemanha", "Escala": unit, "Valor": "7"}))
    lines.append(row(**{"Ano": "2024", "Nome Região (Portugal)": "Portugal", "Escala": unit, "Valor": "9999"}))
    for position, name in enumerate(municipalities):
        for year in years:
            value, symbol = str(100 + position * 10 + (year - years[0]) + value_offset), ""
            if with_symbols and year == years[-1]:
                if position == 0:
                    value, symbol = "", "x"
                elif position == 1:
                    symbol = "r"
            lines.append(row(**{
                "Ano": str(year), "Nome Região (Portugal)": name, "Âmbito Geográfico": "Município",
                "Filtro 1": filter_1, "Símbolo": symbol, "Escala": unit, "Valor": value,
            }))
    return "\n".join(lines) + "\n"


def offline_downloader(texts_by_url: Mapping[str, str], *, failing: Mapping[str, Exception] | None = None):
    """Substitui o `HttpDownloader`: grava o texto do URL pedido, ou levanta o erro configurado."""
    failing = failing or {}

    def download(url: str, destination: Path) -> Path:
        if url in failing:
            raise failing[url]
        Path(destination).write_text(texts_by_url[url], encoding="utf-8", newline="")
        return Path(destination)

    return download
