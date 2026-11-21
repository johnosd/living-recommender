"""Validação da resposta 1x1 (spec 009, FR-016, research R3)."""
import json

import pytest

from pipelines.collectors.mobility.validate import validate_routes_response
from tests.fixtures.mobility.responses import (
    routes_element_error,
    routes_not_found,
    routes_ok,
)


def check(tmp_path, body):
    path = tmp_path / "response.json"
    path.write_text(body, encoding="utf-8")
    validate_routes_response({}, path)


def element(**changes):
    base = {"originIndex": 0, "destinationIndex": 0, "distanceMeters": 1000, "duration": "60s",
            "condition": "ROUTE_EXISTS"}
    base.update(changes)
    return json.dumps([base])


@pytest.mark.parametrize("body", [
    routes_ok(), routes_not_found(), element(status={}), element(status={"code": 0}),
    element(duration="3600.5s"), element(distanceMeters=0),
])
def test_valid_answers_are_accepted(tmp_path, body):
    check(tmp_path, body)


@pytest.mark.parametrize(("body", "message"), [
    ("", "vazia"),
    ("não é json", "não é JSON"),
    ("{}", "lista de um elemento"),
    ("[]", "lista de um elemento"),
    (json.dumps([{}, {}]), "lista de um elemento"),
    (json.dumps(["x"]), "lista de um elemento"),
    (routes_element_error(), "status 8"),
    (element(status={"code": 7, "message": "denied"}), "status 7"),
    (element(originIndex=1), "índices"),
    (element(destinationIndex=2), "índices"),
    (element(condition="ROUTE_UNKNOWN"), "condition"),
    (json.dumps([{"originIndex": 0, "destinationIndex": 0}]), "condition"),
    (element(distanceMeters=None), "distanceMeters"),
    (element(distanceMeters=-1), "distanceMeters"),
    (element(distanceMeters="12"), "distanceMeters"),
    (element(distanceMeters=True), "distanceMeters"),
    (element(duration="15m"), "duration"),
    (element(duration=900), "duration"),
    (element(duration=None), "duration"),
])
def test_invalid_answers_are_rejected_with_a_reason(tmp_path, body, message):
    with pytest.raises(ValueError, match=message):
        check(tmp_path, body)


def test_the_error_message_is_truncated_so_a_server_echo_cannot_flood_the_manifest(tmp_path):
    long = json.dumps([{"originIndex": 0, "destinationIndex": 0, "status": {"code": 8, "message": "x" * 5000}}])
    with pytest.raises(ValueError, match="status 8") as error:
        check(tmp_path, long)
    assert len(str(error.value)) < 200
