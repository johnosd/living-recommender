"""Planilha sintética no layout real da exportação do Pordata (poder de compra per capita, NUTS 2013)."""

from collections.abc import Sequence
from pathlib import Path

from openpyxl import Workbook

HEADER_ROW = 12  # linha do cabeçalho `Âmbito Geográfico | Anos | <anos>` na exportação real


def make_pordata_xlsx(
    path: Path,
    names: Sequence[str],
    *,
    years: Sequence[int] = (2019, 2021),
    missing: dict[tuple[str, int], object] | None = None,
    value_offset: float = 0.0,
    sheets: Sequence[str] = ("Quadro", "Metainformação", "Alterações NUTS"),
    with_header: bool = True,
) -> Path:
    """Grava a planilha: abas, título, 4 linhas NUTS, uma linha `Município` por nome e o rodapé de símbolos.

    ``missing`` troca o valor de ``(nome, ano)`` por outro conteúdo (``None`` = célula vazia, ``"x"`` = símbolo).
    ``sheets`` e ``with_header`` permitem fabricar planilhas inválidas.
    """
    missing = missing or {}
    workbook = Workbook()
    workbook.remove(workbook.active)
    for title in sheets:
        workbook.create_sheet(title)
    if "Quadro" in sheets:
        quadro = workbook["Quadro"]
        quadro["C7"] = "Poder de compra per capita"
        quadro["C9"] = "Número índice - %"
        quadro["A10"], quadro["C10"] = "Territórios", "Poder de compra"
        if with_header:
            quadro.cell(HEADER_ROW, 1, "Âmbito Geográfico")
            quadro.cell(HEADER_ROW, 2, "Anos")
            for column, year in enumerate(years, start=3):
                quadro.cell(HEADER_ROW, column, str(year))  # a exportação real guarda os anos como texto
        row = HEADER_ROW + 1
        for scope, name in (("NUTS 2013", "Portugal"), ("NUTS I", "Continente"), ("NUTS II", "Norte"),
                            ("NUTS III", "Alto Minho")):
            for column, _ in enumerate(years, start=3):
                quadro.cell(row, column, 100.0)
            quadro.cell(row, 1, scope)
            quadro.cell(row, 2, name)
            row += 1
        for index, name in enumerate(names):
            quadro.cell(row, 1, "Município")
            quadro.cell(row, 2, name)
            for column, year in enumerate(years, start=3):
                quadro.cell(row, column, missing.get((name, year), round(50 + index * 0.5 + (year - years[0]) + value_offset, 1)))
            row += 1
        quadro.cell(row, 1, "N")
        quadro.cell(row, 2, "Valor negligenciável")
        quadro.cell(row + 1, 1, "Dados obtidos em https:www.pordata.pt a 29-02-2024")
    workbook.save(path)
    return Path(path)
