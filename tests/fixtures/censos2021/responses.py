"""Fixtures sintéticas no formato INE observado em 2026-11-13; travadas na spec 006."""

import json
from copy import deepcopy
from urllib.parse import parse_qs, urlparse

import pandas as pd

from tests.fixtures.ine.responses import ine_response

BASE = "https://www.ine.pt/ine/json_indicador/"
AGES = (("T", "Total", None, None), ("32", "25 - 29 anos", 25, 29),
        ("41", "30 - 34 anos", 30, 34), ("42", "35 - 39 anos", 35, 39),
        ("72", "65 - 69 anos", 65, 69), ("81", "70 - 74 anos", 70, 74),
        ("82", "75 - 79 anos", 75, 79), ("91", "80 - 84 anos", 80, 84),
        ("92", "85 e mais anos", 85, None))


def dataset(age="T"):
    return {"id": f"pop_2025_{age}", "indicator": "0014632", "collection_method": "api_json",
            "api_url": BASE + "pindica.jsp", "role": "data", "format": "json",
            "geography_version": "2025", "reference_period": "2021", "age_code": age,
            "metadata_dataset_id": "meta_2025",
            "params": {"Dim1": "S7A2021", "Dim2": "lvl@6", "Dim3": "T", "Dim4": age, "Dim5": "T"}}


def metadata():
    cats = {f"Dim_Num4_{code}": [{"dim_num": "4", "cat_id": code, "categ_cod": code,
                                  "categ_dsg": label}] for code, label, _, _ in AGES}
    return {"IndicadorCod": "0014632", "IndicadorNome": "População residente, geografia 2025",
            "PrimeiroPeriodo": "2021", "UltimoPeriodo": "2021", "PrecisaoDecimal": "0",
            "DataUltimaAtualizacao": "2026-02-05", "DataExtracao": "2026-11-13T12:00:00Z",
            "Dimensoes": {"Descricao_Dim": [{"dim_num": "2", "versao": "05723"},
                                             {"dim_num": "4", "versao": "00708"}],
                          "Categoria_Dim": [cats]}, "Sucesso": {"Verdadeiro": [{"Msg": "OK"}]}}


def response(age="T", *, values=None, extracted="2026-11-13T12:00:00Z"):
    doc = json.loads(ine_response("0014632", periods=("2021",), missing=()))[0]
    label = next(label for code, label, _, _ in AGES if code == age)
    rows = []
    for code, value in (values or {"010103": 100, "0308FC": 0}).items():
        row = {"geocod": code, "geodsg": "Freguesia sintética", "dim_3": "T", "dim_3_t": "HM",
               "dim_4": age, "dim_4_t": label, "dim_5": "T", "dim_5_t": "Total"}
        if value is None:
            row.update(sinal_conv="x", sinal_conv_desc="Dado confidencial", ind_string="x")
        else:
            row.update(valor=str(value), ind_string=str(value))
        rows.append(row)
    doc.update(Dados={"2021": rows}, DataExtracao=extracted)
    return json.dumps([doc], ensure_ascii=False).encode()


def catalog():
    return {"sources": {"censos": {"id": "censos", "publisher": "INE", "responsible_party": "projeto",
            "license_id": "CC-BY-4.0", "attribution": "INE — Censos 2021",
            "collection_method": "api_json", "frequency": "por revisão", "territorial_level": "freguesia",
            "datasets": [{"id": "meta_2025", "role": "metadata", "format": "json",
                          "collection_method": "http_download", "indicator": "0014632",
                          "geography_version": "2025", "reference_period": "2021",
                          "origin": BASE + "pindicaMeta.jsp?varcd=0014632&lang=PT"},
                         dataset("T"), dataset("32")]}}}


def downloader(*, changed=False, invalid=False, extracted="2026-11-13T12:00:00Z"):
    def fetch(url, destination):
        query = parse_qs(urlparse(url).query)
        if "pindicaMeta" in url:
            doc = deepcopy(metadata()); doc["DataExtracao"] = extracted
            content = json.dumps([doc], ensure_ascii=False).encode()
        else:
            assert query["Dim1"] == ["S7A2021"] and query["Dim2"] == ["lvl@6"]
            assert query["Dim3"] == ["T"] and query["Dim5"] == ["T"]
            age = query["Dim4"][0]
            content = b"<html>erro</html>" if invalid and age == "32" else response(
                age, values={"010103": 101 if changed and age == "32" else 100, "0308FC": 0},
                extracted=extracted,
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    return fetch


def territory_frames():
    parishes = pd.DataFrame({"dicofre": ["010103", "0308FC", "0308FD", "021123"],
                             "dico": ["0101", "0308", "0308", "0211"], "caop_version": ["2025"] * 4})
    categories = pd.DataFrame({"age_code": ["T", "32"], "age_min": [None, 25],
                               "age_max": [None, 29], "is_total": [True, False]})
    crosswalk = pd.DataFrame([
        ("010103", "010103", "one_to_one", False),
        ("030880", "0308FC", "one_to_many", False),
        ("030880", "0308FD", "one_to_many", False),
        ("021118", "021123", "many_to_many", True),
        ("021122", "021123", "many_to_many", True),
    ], columns=["dicofre_2013", "dicofre_2025", "relation", "partial_origin"])
    rows = []
    for age in ("T", "32"):
        for code, geo, value in [("010103", "2025", 100), ("0308FC", "2025", 11),
                                 ("030880", "2013", 300), ("021118", "2013", 50),
                                 ("021122", "2013", 60)]:
            rows.append({"source_dicofre": code, "geography_version": geo, "period": "2021",
                         "age_code": age, "value": value, "value_status": "observed",
                         "dataset_id": f"synthetic_{geo}_{age}"})
    return pd.DataFrame(rows), parishes, crosswalk, categories
