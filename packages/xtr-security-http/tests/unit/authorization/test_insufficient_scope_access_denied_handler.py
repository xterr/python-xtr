"""The insufficient-scope handler answers with an RFC 6750 scope challenge."""

from __future__ import annotations

import pytest
from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core.exception import AccessDeniedError

from tests.support.messages import make_message
from xtr_security_http.authorization.insufficient_scope_access_denied_handler import (
    InsufficientScopeAccessDeniedHandler,
)
from xtr_security_http.authorization.oauth2_scope_voter import oauth2_scope

pytestmark = pytest.mark.anyio


async def test_it_names_the_missing_scope_and_realm() -> None:
    error = AccessDeniedError(attributes=(oauth2_scope("books:read", "books:write"),))

    response = await InsufficientScopeAccessDeniedHandler(ResponseFactory(), realm="shop").handle(
        make_message(), error
    )

    assert response is not None
    assert response.get_status_code() == 403
    challenge = response.get_header_line("www-authenticate")
    assert 'realm="shop"' in challenge
    assert 'error="insufficient_scope"' in challenge
    assert 'scope="books:read books:write"' in challenge


async def test_it_omits_the_realm_when_unset() -> None:
    error = AccessDeniedError(attributes=(oauth2_scope("books:read"),))

    response = await InsufficientScopeAccessDeniedHandler(ResponseFactory()).handle(
        make_message(), error
    )

    assert response is not None
    assert "realm=" not in response.get_header_line("www-authenticate")


async def test_a_non_scope_denial_carries_no_scope() -> None:
    error = AccessDeniedError(attributes=("ROLE_ADMIN",))

    response = await InsufficientScopeAccessDeniedHandler(ResponseFactory()).handle(
        make_message(), error
    )

    assert response is not None
    assert "scope=" not in response.get_header_line("www-authenticate")


async def test_the_challenge_is_not_cached() -> None:
    error = AccessDeniedError(attributes=(oauth2_scope("books:read"),))

    response = await InsufficientScopeAccessDeniedHandler(ResponseFactory()).handle(
        make_message(), error
    )

    assert response is not None
    assert response.get_header_line("cache-control") == "no-store"
    assert response.get_header_line("pragma") == "no-cache"
