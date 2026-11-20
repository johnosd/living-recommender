from copy import deepcopy

import pytest

from pipelines.collectors.wikipedia.catalog import wikipedia_source
from tests.fixtures.wikipedia.responses import catalog


def test_wikipedia_explicit_universe_and_default_public_contact():
    assert wikipedia_source(catalog(7))["expected_municipalities"] == 7


@pytest.mark.parametrize("field,value", [
    ("contact", ""), ("contact", None), ("contact", "anonymous"),
    ("language", "en"), ("api_url", "https://example.org/w/api.php"),
    ("robots_exception", "allow_all"), ("min_interval_seconds", 0.9),
    ("license_id", "MIT"), ("expected_municipalities", 0), ("maxlag", 0),
    ("min_interval_seconds", float("nan")), ("timeout_seconds", float("inf")),
    ("max_attempts", 4), ("max_attempts", 0), ("license_url", "https://example.test/mit"),
])
def test_wikipedia_rejects_unsafe_source(field, value):
    data = deepcopy(catalog())
    data["sources"]["wikipedia"][field] = value
    with pytest.raises(ValueError):
        wikipedia_source(data)
