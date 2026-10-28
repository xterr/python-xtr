"""The failure response carries the code, message and bearer challenge."""

from __future__ import annotations

import json
from typing import cast

import pytest
from xtr_http_kernel.bridge import ResponseFactory

from xtr_security_jwt.response.jwt_authentication_failure_response import (
    jwt_authentication_failure_response,
)

pytestmark = pytest.mark.anyio


async def test_it_defaults_to_401_with_a_bearer_challenge() -> None:
    response = await jwt_authentication_failure_response(
        ResponseFactory(),
        "JWT Token not found",
    )

    assert response.get_status_code() == 401
    assert response.get_header_line("www-authenticate") == "Bearer"


async def test_its_body_is_the_code_and_message() -> None:
    response = await jwt_authentication_failure_response(
        ResponseFactory(),
        "Invalid JWT Token",
    )

    body = cast("dict[str, object]", json.loads(await response.get_body().get_contents()))
    assert body == {"code": 401, "message": "Invalid JWT Token"}


async def test_it_forbids_every_cache_from_keeping_the_refusal() -> None:
    response = await jwt_authentication_failure_response(
        ResponseFactory(),
        "Invalid JWT Token",
    )

    assert response.get_header_line("cache-control") == "no-store"
    assert response.get_header_line("pragma") == "no-cache"
