"""The failure response carries the code, message and bearer challenge."""

from __future__ import annotations

import json
from typing import cast

from starlette.responses import JSONResponse

from xtr_security_jwt.response.jwt_authentication_failure_response import (
    JwtAuthenticationFailureResponse,
)


def test_it_is_a_json_response() -> None:
    assert JSONResponse in JwtAuthenticationFailureResponse.__mro__


def test_it_defaults_to_401_with_a_bearer_challenge() -> None:
    response = JwtAuthenticationFailureResponse("JWT Token not found")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_its_body_is_the_code_and_message() -> None:
    response = JwtAuthenticationFailureResponse("Invalid JWT Token")

    body = cast("dict[str, object]", json.loads(bytes(response.body)))
    assert body == {"code": 401, "message": "Invalid JWT Token"}
    assert response.get_message() == "Invalid JWT Token"
