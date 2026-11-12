"""Planilhas sintéticas no layout real das duas tabelas do INE (verificadas em 2026-11-12) e o cenário de teste.

- Tabela A (`CorrespondenciasAntes-Depois-R2013.xlsx`): aba `Correspondências 2013`, cabeçalho na linha 1.
- Tabela B (`Codificação_FR_Repostas 2025_2013_Julho.xlsx`): aba `Sheet1`; o rótulo do código de 2025 tem
  dois espaços (`Código -  Freguesias repostas em 2025`), como na planilha real.

O cenário cobre, em 19 pares, todos os casos que a derivação precisa acertar. Os códigos 2013/2025 aceitam
letras (`0308FC`, criados pelo INE) e as células de código podem ser números inteiros de 6 dígitos (51 células
nas planilhas reais), por isso as linhas `110640`/`110658` são ``int`` de propósito.
"""

from collections.abc import Sequence
from pathlib import Path

import pandas as pd
from openpyxl import Workbook

SOURCE_ID = "ine_parish_crosswalk"
SHEET_A, SHEET_B = "Correspondências 2013", "Sheet1"
LABELS_A = {
    "pre_code": "Código",
    "pre_name": "Freguesias antes da Reorganização",
    "name": "Freguesias - Reorganização de 2013",
    "code": "Código Novo",
}
LABELS_B = {
    "pre_code": "Código - Freguesias antes da reorganização administrativa de 2013",
    "pre_name": "Designação - Freguesias antes da reorganização administrativa de 2013",
    "municipality_name": "Designação - Município",
    "code": "Código -  Freguesias repostas em 2025",
    "name": "Designação - Freguesias repostas em 2025",
}
URL_A, URL_B = "https://example.test/Versao/Download/9160", "https://example.test/Versao/Download/10698"

UNION_1 = "União das freguesias de Belazaima do Chão, Castanheira do Vouga e Agadão"
UNION_2 = "União das freguesias de Alfa e Beta"
UNION_3 = "União das freguesias de Serzedo e Tabuadelo"

# (código pré-2013, designação pré-2013, designação 2013, código 2013)
ROWS_A: list[tuple] = [
    ("010103", "Aguada de Cima", "Aguada de Cima", "010103"),                   # 1:1
    ("010101", "Agadão", UNION_1, "010123"),                                    # união desfeita em 3
    ("010106", "Belazaima do Chão", UNION_1, "010123"),
    ("010107", "Castanheira do Vouga", UNION_1, "010123"),
    ("010201", "Alfa", UNION_2, "010210"),                                      # união de 2; só Alfa é reposta
    ("010202", "Beta", UNION_2, "010210"),
    ("021103", "Colos", "Colos", "021118"),                                     # "(parte)" repartida em duas
    ("021113", "Bicos (parte)", "Colos", "021118"),
    ("021120", "Vale de Santiago", "Vale de Santiago", "021122"),
    ("021113", "Bicos (parte)", "Vale de Santiago", "021122"),
    ("030867", "Serzedo", UNION_3, "030880"),                                   # destinos alfanuméricos
    ("030869", "Tabuadelo", UNION_3, "030880"),
    (110640, "São Francisco Xavier", "Belém", 110658),                          # células numéricas
    ("110633", "Santa Maria dos Olivais", "Olivais", "110633"),                 # "(parte)" que fica 1:1
    ("110633", "Santa Maria dos Olivais (parte)", "Parque das Nações", "110662"),
    ("050101", "Velha", "Velha", "050101"),                                     # só a designação muda em 2025
    ("060101", "Mudada", "Mudada", "060101"),                                   # muda de município em 2025
    ("090101", "Um", "Um", "090101"),                                           # duas viram uma (N:1)
    ("090102", "Dois", "Dois", "090102"),
]
# (código pré-2013, designação pré-2013, município, código 2025, designação 2025)
ROWS_B: list[tuple] = [
    ("010101", "Agadão", "Águeda", "010128", "Agadão"),
    ("010106", "Belazaima do Chão", "Águeda", "010132", "Belazaima do Chão"),
    ("010107", "Castanheira do Vouga", "Águeda", "010133", "Castanheira do Vouga"),
    ("010201", "Alfa", "Alfaville", "010230", "Alfa"),
    ("021113", "Bicos", "Odemira", "021123", "Bicos"),
    ("030867", "Serzedo", "Guimarães", "0308FC", "Serzedo"),
    ("030869", "Tabuadelo", "Guimarães", "0308FD", "Tabuadelo"),
    ("050101", "Velha", "Cidade Nova", "050199", "Nova"),
    ("060101", "Mudada", "Outro", "070150", "Mudada"),
    ("090101", "Um", "Junta", "090150", "Junta"),
    ("090102", "Dois", "Junta", "090150", "Junta"),
]


def _workbook(path: Path, sheet: str, header: Sequence[str], rows: Sequence[Sequence]) -> Path:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet
    worksheet.append(list(header))
    for row in rows:
        worksheet.append(list(row))
    workbook.save(path)
    return Path(path)


def make_table_a(path: Path, rows: Sequence[Sequence] | None = None, *, sheet: str = SHEET_A,
                 labels: dict[str, str] | None = None, extra: Sequence[Sequence] = ()) -> Path:
    """Grava a tabela A. ``extra`` são linhas anexadas ao final (legenda, linha vazia, código inválido)."""
    labels = labels or LABELS_A
    header = [labels["pre_code"], labels["pre_name"], labels["name"], labels["code"]]
    return _workbook(path, sheet, header, [*(ROWS_A if rows is None else rows), *extra])


def make_table_b(path: Path, rows: Sequence[Sequence] | None = None, *, sheet: str = SHEET_B,
                 labels: dict[str, str] | None = None, extra: Sequence[Sequence] = ()) -> Path:
    labels = labels or LABELS_B
    header = [labels["pre_code"], labels["pre_name"], labels["municipality_name"], labels["code"], labels["name"]]
    return _workbook(path, sheet, header, [*(ROWS_B if rows is None else rows), *extra])


def catalog() -> dict:
    """Catálogo mínimo da fonte `ine_parish_crosswalk`, com as duas tabelas e o mapa de colunas por rótulo."""
    return {SOURCE_ID: {
        "id": SOURCE_ID, "license_id": "CC-BY-4.0", "collection_method": "http_download",
        "attribution": "Instituto Nacional de Estatística, IP – Portugal",
        "datasets": [
            {"id": "reorganizacao_2013", "origin": URL_A, "format": "xlsx", "role": "pre2013_to_2013",
             "sheet": SHEET_A, "columns": dict(LABELS_A)},
            {"id": "reposicao_2025", "origin": URL_B, "format": "xlsx", "role": "pre2013_to_2025",
             "sheet": SHEET_B, "columns": dict(LABELS_B)},
        ],
    }}


def dataset(dataset_id: str) -> dict:
    """O dataset já resolvido do catálogo de teste (``collection_method`` herdado da fonte)."""
    source = catalog()[SOURCE_ID]
    found = next(item for item in source["datasets"] if item["id"] == dataset_id)
    return {"collection_method": source["collection_method"], **found}


def offline_downloader(payloads: dict[str, bytes]):
    """`downloader(url, destino)` que grava os bytes do dicionário; recusa URL fora dele."""

    def download(url: str, destination: str | Path) -> Path:
        destination = Path(destination)
        destination.write_bytes(payloads[url])
        return destination

    return download


def payloads(tmp_path: Path, *, rows_a=None, rows_b=None) -> dict[str, bytes]:
    a = make_table_a(tmp_path / "a-fixture.xlsx", rows_a)
    b = make_table_b(tmp_path / "b-fixture.xlsx", rows_b)
    return {URL_A: a.read_bytes(), URL_B: b.read_bytes()}


def _code(value) -> str:
    return str(int(value)) if isinstance(value, (int, float)) else str(value).strip()


def scenario_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    """As tabelas A e B já normalizadas (o que `read_crosswalk_table` devolve), sem passar por planilha."""
    table_a = pd.DataFrame(
        [(_code(p), n, nome, _code(c), n.casefold().endswith("(parte)")) for p, n, nome, c in ROWS_A],
        columns=["pre_code", "pre_name", "name_2013", "code_2013", "partial_origin"],
    )
    table_b = pd.DataFrame(
        [(_code(p), n, m, _code(c), nome) for p, n, m, c, nome in ROWS_B],
        columns=["pre_code", "pre_name", "municipality_name", "code_2025", "name_2025"],
    )
    return table_a, table_b
