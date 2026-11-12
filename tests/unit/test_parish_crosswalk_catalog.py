"""Entrada `ine_parish_crosswalk` do catálogo real (spec 004, FR-001 e FR-019)."""

import copy

import pytest

from pipelines.collectors._shared.catalog import (
    CatalogError,
    get_dataset_source,
    load_catalog,
)

SOURCE = "ine_parish_crosswalk"


def test_real_catalog_declares_the_two_ine_tables_with_sheet_role_and_column_labels():
    source = get_dataset_source(load_catalog(), SOURCE, strict_metadata=True)
    assert source["license_id"] and source["attribution"] == "Instituto Nacional de Estatística, IP – Portugal"
    assert source["collection_method"] == "http_download" and source["frequency"] == "on_demand"
    datasets = {dataset["id"]: dataset for dataset in source["datasets"]}
    assert set(datasets) == {"reorganizacao_2013", "reposicao_2025"}
    for dataset in datasets.values():
        assert dataset["format"] == "xlsx" and dataset["sheet"] and dataset["columns"]
        assert dataset["origin"].startswith("https://smi.ine.pt/Versao/Download/")
    assert datasets["reorganizacao_2013"]["role"] == "pre2013_to_2013"
    assert set(datasets["reorganizacao_2013"]["columns"]) == {"pre_code", "pre_name", "name", "code"}
    assert datasets["reposicao_2025"]["role"] == "pre2013_to_2025"
    assert set(datasets["reposicao_2025"]["columns"]) == {"pre_code", "pre_name", "municipality_name", "code", "name"}


def test_a_non_https_origin_is_refused_before_any_network_access():
    catalog = copy.deepcopy(load_catalog())
    catalog["sources"][SOURCE]["datasets"][0]["origin"] = "http://smi.ine.pt/Versao/Download/9160"
    with pytest.raises(CatalogError, match="HTTPS"):
        get_dataset_source(catalog, SOURCE)


def test_a_source_that_is_not_in_the_catalog_is_refused():
    with pytest.raises(CatalogError, match="não cadastrada"):
        get_dataset_source(load_catalog(), "fonte_que_nao_existe")
