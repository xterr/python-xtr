"""The exception listener turns a security error into a response, or leaves it be."""

from __future__ import annotations

import pytest
from xtr_security_core.authentication.authentication_trust_resolver import (
    AuthenticationTrustResolver,
)
from xtr_security_core.exception import AccessDeniedError, BadCredentialsError

from tests.support.requests import make_request
from xtr_security_http._state import CarriedResponse
from xtr_security_http.firewall.exception_listener import ExceptionListener

pytestmark = pytest.mark.anyio


def _listener() -> ExceptionListener:
    return ExceptionListener(AuthenticationTrustResolver())


async def test_a_non_security_exception_is_left_alone() -> None:
    from xtr_http_kernel import ExceptionEvent  # noqa: PLC0415

    event = ExceptionEvent(make_request(), RuntimeError("boom"))

    await _listener().on_exception(event)

    assert event.response is None


async def test_a_carried_response_is_sent() -> None:
    from starlette.responses import JSONResponse  # noqa: PLC0415
    from xtr_http_kernel import ExceptionEvent  # noqa: PLC0415

    response = JSONResponse({"ok": True})
    event = ExceptionEvent(make_request(), CarriedResponse(response))

    await _listener().on_exception(event)

    assert event.response is response


async def test_an_authentication_error_without_a_firewall_is_a_bare_challenge() -> None:
    from xtr_http_kernel import ExceptionEvent  # noqa: PLC0415

    event = ExceptionEvent(make_request(), BadCredentialsError())

    await _listener().on_exception(event)

    assert event.response is not None
    assert event.response.status_code == 401
    assert event.response.headers["www-authenticate"] == "Bearer"
    assert event.response.headers["cache-control"] == "no-store"
    assert event.response.headers["pragma"] == "no-cache"


async def test_an_access_denied_without_a_firewall_challenges() -> None:
    from xtr_http_kernel import ExceptionEvent  # noqa: PLC0415

    event = ExceptionEvent(make_request(), AccessDeniedError(attributes=("ROLE_ADMIN",)))

    await _listener().on_exception(event)

    assert event.response is not None
    assert event.response.status_code == 401


async def test_a_full_fledged_denial_without_a_handler_is_an_uncached_403() -> None:
    from fastapi.security import HTTPBearer  # noqa: PLC0415
    from xtr_http_kernel import ExceptionEvent  # noqa: PLC0415
    from xtr_security_core.user import InMemoryUser  # noqa: PLC0415

    from tests.support.contexts import FakeFirewallContext  # noqa: PLC0415
    from xtr_security_http._state import FIREWALL_CONTEXT_KEY, TOKEN_KEY  # noqa: PLC0415
    from xtr_security_http.authenticator.token import PostAuthenticationToken  # noqa: PLC0415

    request = make_request()
    context = FakeFirewallContext(
        name="api",
        authenticator_manager=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        access_listener=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        scheme=HTTPBearer(auto_error=False),
    )
    setattr(request.state, FIREWALL_CONTEXT_KEY, context)
    setattr(
        request.state,
        TOKEN_KEY,
        PostAuthenticationToken(InMemoryUser("alice"), "api", ["ROLE_USER"]),
    )
    event = ExceptionEvent(request, AccessDeniedError(attributes=("ROLE_ADMIN",)))

    await _listener().on_exception(event)

    assert event.response is not None
    assert event.response.status_code == 403
    assert event.response.headers["cache-control"] == "no-store"
    assert event.response.headers["pragma"] == "no-cache"
