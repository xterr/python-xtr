"""The exception listener turns a security error into a response, or leaves it be."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from starlette.responses import Response as FrameworkResponse
from xtr_http_kernel import ExceptionEvent
from xtr_http_kernel.bridge import Response as KernelResponse
from xtr_http_kernel.bridge import ResponseFactory, StarletteHttpFactory
from xtr_http_message import Response as PureResponse
from xtr_security_core.authentication.authentication_trust_resolver import (
    AuthenticationTrustResolver,
)
from xtr_security_core.exception import AccessDeniedError, BadCredentialsError
from xtr_security_core.user import InMemoryUser

from tests.support.contexts import FakeFirewallContext
from tests.support.messages import make_message
from xtr_security_http._security_state import CarriedResponse, security_state_of
from xtr_security_http.authenticator.token import PostAuthenticationToken
from xtr_security_http.firewall.exception_listener import ExceptionListener

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.exception import AuthenticationError

pytestmark = pytest.mark.anyio


@final
class _ChallengingEntryPoint:
    """Answers with the response it was built to return."""

    def __init__(self, response: ResponseInterface) -> None:
        self._response = response

    async def start(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError | None = None,
    ) -> ResponseInterface:
        del request, error
        return self._response


def _listener() -> ExceptionListener:
    return ExceptionListener(
        AuthenticationTrustResolver(),
        ResponseFactory(),
        StarletteHttpFactory(),
    )


def _event(error: BaseException, bag: dict[str, object] | None = None) -> ExceptionEvent:
    return ExceptionEvent(make_message(), bag or {}, error)


def _context(entry_point: ResponseInterface | None = None) -> FakeFirewallContext:
    return FakeFirewallContext(
        name="api",
        authenticator_manager=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        access_listener=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        scheme=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        entry_point=_ChallengingEntryPoint(entry_point) if entry_point is not None else None,
    )


async def test_a_non_security_exception_is_left_alone() -> None:
    event = _event(RuntimeError("boom"))

    await _listener().on_exception(event)

    assert event.response is None


async def test_a_carried_response_is_sent() -> None:
    response = ResponseFactory().create_response(200)
    event = _event(CarriedResponse(response))

    await _listener().on_exception(event)

    assert event.response is response


async def test_an_authentication_error_without_a_firewall_is_a_bare_challenge() -> None:
    event = _event(BadCredentialsError())

    await _listener().on_exception(event)

    assert event.response is not None
    assert event.response.status_code == 401
    assert event.response.headers["www-authenticate"] == "Bearer"
    assert event.response.headers["cache-control"] == "no-store"
    assert event.response.headers["pragma"] == "no-cache"
    assert isinstance(event.response, KernelResponse)
    assert await event.response.get_body().get_contents() == b'{"error":"unauthorized"}'


async def test_an_access_denied_without_a_firewall_challenges() -> None:
    event = _event(AccessDeniedError(attributes=("ROLE_ADMIN",)))

    await _listener().on_exception(event)

    assert event.response is not None
    assert event.response.status_code == 401


async def test_a_full_fledged_denial_without_a_handler_is_an_uncached_403() -> None:
    bag: dict[str, object] = {}
    state = security_state_of(bag)
    state.firewall_context = _context()
    state.token = PostAuthenticationToken(InMemoryUser("alice"), "api", ["ROLE_USER"])
    event = _event(AccessDeniedError(attributes=("ROLE_ADMIN",)), bag)

    await _listener().on_exception(event)

    assert event.response is not None
    assert event.response.status_code == 403
    assert event.response.headers["cache-control"] == "no-store"
    assert event.response.headers["pragma"] == "no-cache"


async def test_a_pure_message_from_an_entry_point_is_converted_to_what_the_event_accepts() -> None:
    pure = PureResponse(401, None, None, "1.1").with_header("location", "/login")
    bag: dict[str, object] = {}
    security_state_of(bag).firewall_context = _context(pure)
    event = _event(BadCredentialsError(), bag)

    await _listener().on_exception(event)

    assert event.response is not None
    assert event.response is not pure
    assert isinstance(event.response, FrameworkResponse)
    assert event.response.status_code == 401
    assert event.response.headers["location"] == "/login"


async def test_a_kernel_response_from_an_entry_point_is_sent_as_it_is() -> None:
    dual = ResponseFactory().create_response(401).with_header("location", "/login")
    bag: dict[str, object] = {}
    security_state_of(bag).firewall_context = _context(dual)
    event = _event(BadCredentialsError(), bag)

    await _listener().on_exception(event)

    assert event.response is dual
