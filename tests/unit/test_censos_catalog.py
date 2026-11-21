"""Catálogo nacional censitário e proteção contra seletores incorretos."""

from copy import deepcopy

import pytest

from pipelines.collectors._shared.catalog import get_dataset_source, load_catalog
from pipelines.collectors.censos2021.validate import validate_censos_catalog
from tests.fixtures.censos2021.responses import catalog


def test_national_catalog_has_201_items_and_two_metadata_families():
    source = validate_censos_catalog(load_catalog())
    assert len(source["datasets"]) == 201
    assert sum(d["role"] == "metadata" for d in source["datasets"]) == 2
    assert len({d["id"] for d in source["datasets"]}) == 201
    for indicator, count in [("0014632", 3259), ("0011719", 3092)]:
        family = [
            d
            for d in source["datasets"]
            if d["role"] == "data" and d["indicator"] == indicator
        ]
        codes = [c for d in family for c in d["parish_codes"]]
        assert len(codes) == len(set(codes)) == count
        assert all(1 <= len(d["parish_codes"]) <= 32 for d in family)
    assert (
        get_dataset_source(load_catalog(), "ine")["datasets"][0]["params"]["Dim2"]
        == "lvl@5"
    )


@pytest.mark.parametrize(
    "field,value", [("Dim1", "2021"), ("Dim3", "1"), ("Dim4", "ALL"), ("Dim5", "PT")]
)
def test_invalid_selectors_fail_before_network(field, value):
    config = deepcopy(catalog())
    config["sources"]["censos"]["datasets"][1]["params"][field] = value
    with pytest.raises(ValueError):
        validate_censos_catalog(config)
