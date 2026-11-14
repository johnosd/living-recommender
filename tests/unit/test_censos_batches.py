"""Lotes explícitos: cobertura cartesiana, identidade e leitura de várias idades."""

import json
from copy import deepcopy

import pytest

from pipelines.collectors.censos2021.transform import read_censos_response
from pipelines.collectors.censos2021.validate import (
    query_signature,
    validate_censos_catalog,
    validate_censos_response,
)
from tests.fixtures.censos2021.responses import catalog, dataset, metadata, response


def batch():
    d = dataset()
    d.pop("age_code")
    d.update(age_codes=["T", "32"], parish_codes=["010103", "0308FC"])
    d["params"].update(Dim2="010103,0308FC", Dim4="T,32")
    return d


def write_batch(path):
    doc = json.loads(response())
    doc[0]["Dados"]["2021"].extend(json.loads(response("32"))[0]["Dados"]["2021"])
    path.write_text(json.dumps(doc), encoding="utf8")
    return doc


def test_batch_reads_each_native_age_and_preserves_zero(tmp_path):
    p = tmp_path / "batch.json"
    write_batch(p)
    validate_censos_response(batch(), p)
    frame = read_censos_response(batch(), p, metadata())
    assert len(frame) == 4 and set(frame.age_code) == {"T", "32"}
    assert frame.loc[frame.age_code.eq("32"), "age_min"].eq(25).all()
    assert frame.loc[frame.source_dicofre.eq("0308FC"), "value"].eq(0).all()


@pytest.mark.parametrize("case", ["lost", "duplicate", "extra_parish", "extra_age"])
def test_cartesian_batch_rejects_incomplete_or_unrequested_rows(tmp_path, case):
    p = tmp_path / "batch.json"
    doc = write_batch(p)
    rows = doc[0]["Dados"]["2021"]
    if case == "lost":
        rows.pop()
    elif case == "duplicate":
        rows[-1] = deepcopy(rows[0])
    elif case == "extra_parish":
        rows[-1]["geocod"] = "010104"
    else:
        rows[-1]["dim_4"] = "92"
    p.write_text(json.dumps(doc), encoding="utf8")
    with pytest.raises(ValueError):
        validate_censos_response(batch(), p)


@pytest.mark.parametrize("case", ["size", "duplicate", "selector", "age_selector"])
def test_invalid_batch_catalog_is_rejected_before_download(case):
    config = catalog()
    d = batch()
    if case == "size":
        d["parish_codes"] = [f"0101{i:02}" for i in range(33)]
        d["params"]["Dim2"] = ",".join(d["parish_codes"])
    elif case == "duplicate":
        d["parish_codes"] = ["010103", "010103"]
        d["params"]["Dim2"] = "010103,010103"
    elif case == "selector":
        d["params"]["Dim2"] = "010103"
    else:
        d["params"]["Dim4"] = "T"
    config["sources"]["censos"]["datasets"][1:] = [d]
    with pytest.raises(ValueError):
        validate_censos_catalog(config)


def test_batch_signature_changes_when_territorial_selection_changes():
    a = batch()
    b = deepcopy(a)
    b["parish_codes"][1] = "010104"
    b["params"]["Dim2"] = ",".join(b["parish_codes"])
    assert query_signature(a) != query_signature(b)
