"""Normalização por limites oficiais e coerência no suporte de origem."""

import pandas as pd
import pytest

from pipelines.collectors.censos2021.transform import (
    harmonize_age_categories,
    read_censos_response,
)
from pipelines.collectors.censos2021.validate import age_categories
from pipelines.collectors.ine.fetch import build_url
from tests.fixtures.censos2021.ci_seed import (
    fixture_catalog,
    fixture_downloader,
    fixture_metadata,
)
from tests.fixtures.censos2021.responses import dataset, metadata, response


def test_ages_are_read_from_metadata_not_guessed_from_code(tmp_path):
    meta = metadata()
    meta["Dimensoes"]["Categoria_Dim"][0]["Dim_Num4_32"][0]["categ_dsg"] = (
        "30 - 34 anos"
    )
    path = tmp_path / "r.json"
    path.write_bytes(response("32"))
    frame = read_censos_response(dataset("32"), path, meta)
    assert frame.age_min.eq(30).all()
    assert len(age_categories(metadata())) == 9


def test_legacy_85_plus_composes_only_same_origin_and_preserves_suppression():
    frame = pd.DataFrame(
        [
            {
                "source_dicofre": "010103",
                "period": "2021",
                "geography_version": "2013",
                "indicator": "0011719",
                "dataset_id": str(lo),
                "age_code": str(lo),
                "age_min": lo,
                "age_max": hi,
                "is_total": False,
                "value": v,
                "value_status": "observed",
                "is_unknown": False,
            }
            for lo, hi, v in [(85, 89, 20), (90, None, 10)]
        ]
    )
    out = harmonize_age_categories(frame, None)
    assert out.iloc[0]["age_code"] == "85_plus" and out.iloc[0]["value"] == 30
    frame.loc[1, ["value", "value_status"]] = [None, "suppressed"]
    out = harmonize_age_categories(frame, None)
    assert pd.isna(out.iloc[0]["value"]) and out.iloc[0]["value_status"] == "suppressed"
    with pytest.raises(ValueError):
        harmonize_age_categories(frame.iloc[:1], None)


@pytest.mark.parametrize("family", ["0014632", "0011719"])
def test_all_native_age_categories_are_preserved_from_metadata(tmp_path, family):
    configured = fixture_catalog()["sources"]["censos"]
    source = [
        d
        for d in configured["datasets"]
        if d["role"] == "data" and d["indicator"] == family
    ]
    seen = []
    for d in source:
        path = tmp_path / f"{d['id']}.json"
        fixture_downloader(build_url(d), path)
        frame = read_censos_response(d, path, fixture_metadata(family))
        seen.extend(frame.age_code)
        assert frame.loc[~frame.is_total, "age_min"].notna().all()
    assert set(seen) == set(age_categories(fixture_metadata(family)).age_code)
