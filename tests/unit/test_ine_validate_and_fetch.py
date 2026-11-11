"""Validação da resposta do INE, montagem da URL e retentativa após timeout."""

import json

import httpx
import pytest

from pipelines.collectors._shared.catalog import get_dataset_source, load_catalog
from pipelines.collectors._shared.http import (
    HttpDownloader,
    RateLimiter,
    json_content_check,
)
from pipelines.collectors.ine.fetch import build_url, make_ine_fetcher
from pipelines.collectors.ine.validate import IneSchemaError, validate_ine_response
from tests.fixtures.ine.responses import ine_response

DATASETS = {d["id"]: d for d in get_dataset_source(load_catalog(), "ine")["datasets"]}
BASE = "https://www.ine.pt/ine/json_indicador/pindica.jsp"


def test_urls_use_the_municipal_level_all_periods_and_all_crime_categories():
    assert build_url(DATASETS["rendas_novos_contratos"]) == f"{BASE}?op=2&varcd=0014698&Dim1=T&Dim2=lvl@5&lang=PT"
    assert build_url(DATASETS["taxa_criminalidade"]) == (
        f"{BASE}?op=2&varcd=0008074&Dim1=T&Dim2=lvl@5&Dim3=T,1,2,3,4,5,6&lang=PT"
    )
    assert build_url(DATASETS["poder_compra_per_capita"]) == f"{BASE}?op=2&varcd=0014580&Dim1=T&Dim2=lvl@5&lang=PT"


def _write(tmp_path, text):
    path = tmp_path / "r.json"
    path.write_text(text, encoding="utf-8")
    return path


def test_a_valid_response_passes(tmp_path):
    validate_ine_response(DATASETS["rendas_novos_contratos"], _write(tmp_path, ine_response("0014698")))


def _mutated(**changes):
    document = json.loads(ine_response("0014698"))
    document[0].update(changes)
    return json.dumps(document)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("<html>erro</html>", "JSON inválido"),
        ("[]", "sem objeto"),
        (_mutated(Sucesso={"Falso": [{"Msg": "Indicador inexistente"}]}), "Indicador inexistente"),
        (_mutated(IndicadorCod="0000001"), "indicador"),
        (_mutated(Dados={}), "sem dados"),
        (_mutated(Dados={"2025": [{"geocod": "PT", "geodsg": "Portugal", "valor": "1"}]}), "municipal"),
    ],
)
def test_invalid_responses_are_rejected_with_the_reason(tmp_path, text, message):
    with pytest.raises(IneSchemaError, match=message):
        validate_ine_response(DATASETS["rendas_novos_contratos"], _write(tmp_path, text))


def test_timeout_is_retried_with_backoff_and_the_fetcher_reports_period_and_release_date(tmp_path):
    attempts, delays = [], []

    def respond(request):
        attempts.append(str(request.url))
        if len(attempts) == 1:
            raise httpx.ReadTimeout("timed out", request=request)
        return httpx.Response(200, content=ine_response("0014698").encode(),
                              headers={"content-type": "application/json"}, request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        downloader = HttpDownloader(client=client, timeout=90.0, max_attempts=3, backoff=2.0,
                                    rate_limiter=RateLimiter(0), sleep=delays.append,
                                    content_check=json_content_check)
        meta = make_ine_fetcher(downloader)(DATASETS["rendas_novos_contratos"], tmp_path / "r.json")
    assert len(attempts) == 2 and attempts[0] == attempts[1] and delays == [2.0]
    assert meta["reference_period"] == "2025" and meta["source_release_date"] == "2026-09-29"
