"""Respostas sintéticas da API de indicadores do INE, no formato real observado em 2026-11-11."""

import json

# (geocod de 7 caracteres, nome): os 4 últimos caracteres são o `dico` oficial da CAOP.
MUNICIPALITIES = (
    ("1111606", "Ponte da Barca"),   # dico 1606
    ("11A0109", "Santa Maria da Feira"),  # dico 0109
    ("3003101", "Calheta"),          # dico 3101
    ("1C40701", "Alandroal"),        # dico 0701 (sem dado nas rendas)
)
CRIME_CATEGORIES = (("T", "Total"), ("1", "Crimes contra a integridade física"),
                    ("6", "Crimes contra o patrimônio"))


def ine_response(
    indicator: str = "0014698",
    *,
    extracted_at: str = "2026-11-11T18:00:00.000Z",
    periods: tuple[str, ...] = ("2024", "2025"),
    municipalities=MUNICIPALITIES,
    missing: tuple[str, ...] = ("1C40701",),
    categories=None,
    value_offset: float = 0.0,
    published: str = "2026-09-29",
) -> str:
    """Texto JSON de uma resposta: lista com um objeto, `Dados` por período e `Sucesso` OK.

    ``missing`` lista os `geocod` sem valor (vêm com `sinal_conv: "-"`, sem o campo `valor`).
    ``categories`` acrescenta `dim_3`/`dim_3_t` a cada linha, como na criminalidade.
    """
    data = {}
    for p_index, period in enumerate(periods):
        rows = []
        for m_index, (geocod, name) in enumerate(municipalities):
            for code, label in categories or [(None, None)]:
                row = {"geocod": geocod, "geodsg": name}
                if code is not None:
                    row.update({"dim_3": code, "dim_3_t": label})
                if geocod in missing:
                    row.update({"sinal_conv": "-", "sinal_conv_desc": "Dado nulo ou não aplicável",
                                "ind_string": "-"})
                else:
                    value = round(4 + m_index + p_index * 0.5 + value_offset, 2)
                    row.update({"ind_string": str(value).replace(".", ","), "valor": str(value)})
                rows.append(row)
        data[period] = rows
    document = [{
        "IndicadorCod": indicator,
        "IndicadorDsg": f"Indicador sintético {indicator}",
        "MetaInfUrl": f"https://www.ine.pt/bddXplorer/htdocs/minfo.jsp?var_cd={indicator}&lingua=PT",
        "DataExtracao": extracted_at,
        "DataUltimoAtualizacao": published,
        "UltimoPref": periods[-1],
        "Dados": data,
        "Sucesso": {"Verdadeiro": [{"Msg": "OK"}]},
    }]
    return json.dumps(document, ensure_ascii=False, indent=2)
