"""A JSON login served the way a client posts one: the document as the request's body.

The request goes through the kernel's lifecycle middleware, so the chain is
handed the request the kernel serves — connected to its wire, the body unread
— and the real manager runs the real JSON login over it, its credentials
checked by the real credentials listener.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, final

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from xtr_event_dispatcher import EventDispatcher
from xtr_http_foundation import PathRequestMatcher
from xtr_http_kernel import RequestLifecycleMiddleware
from xtr_http_kernel.bridge import ResponseFactory, StarletteHttpFactory
from xtr_password_hasher import PasswordHasherFactory, PlaintextPasswordHasher, UserPasswordHasher
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.user import InMemoryUser

from tests.support.contexts import FakeFirewallContext
from tests.support.served import message_factory, send
from xtr_security_http.authentication.authenticator_manager import AuthenticatorManager
from xtr_security_http.authenticator.json_login_authenticator import JsonLoginAuthenticator
from xtr_security_http.event_listener.check_credentials_listener import CheckCredentialsListener
from xtr_security_http.firewall.authenticator_manager_listener import (
    AuthenticatorManagerListener,
)
from xtr_security_http.firewall.firewall import Firewall
from xtr_security_http.firewall_map import FirewallMap
from xtr_security_http.http_utils import HttpUtils

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.types import ASGIApp
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface

    from xtr_security_http.authentication.authentication_success_handler_interface import (
        AuthenticationSuccessHandlerInterface,
    )

pytestmark = pytest.mark.anyio

_JSON = "application/json"


@final
class _Users:
    """Hands back a user whose password is ``secret``, for any identifier."""

    async def load_user_by_identifier(self, identifier: str) -> UserInterface:
        return InMemoryUser(identifier, password=PlaintextPasswordHasher().hash("secret"))

    async def refresh_user(self, user: UserInterface) -> UserInterface:
        return user

    def supports_class(self, user_class: type) -> bool:
        del user_class
        return True


@final
class _NamingSuccess:
    """Answers a login with the identifier of the user it proved."""

    async def on_authentication_success(
        self, request: ServerRequestInterface, token: TokenInterface
    ) -> ResponseInterface | None:
        del request
        response = ResponseFactory().create_response(200)
        _ = await response.get_body().write(f"logged in {token.get_user_identifier()}".encode())
        return response


@final
class _ContinuingSuccess:
    """Lets the request go on to its route after the login."""

    async def on_authentication_success(
        self, request: ServerRequestInterface, token: TokenInterface
    ) -> ResponseInterface | None:
        del request, token
        return None


async def _echo_body(request: Request) -> PlainTextResponse:
    """Answer with the raw body the route itself reads."""
    return PlainTextResponse(f"route read {(await request.body()).decode()}")


def _application(success_handler: AuthenticationSuccessHandlerInterface) -> ASGIApp:
    """Return an application whose one firewall logs in through a real JSON login."""
    json_login = JsonLoginAuthenticator(
        HttpUtils(ResponseFactory()),
        _Users(),
        ResponseFactory(),
        success_handler,
        options={"check_path": "/api/login"},
    )
    credentials = EventDispatcher()
    hasher = UserPasswordHasher(PasswordHasherFactory({InMemoryUser: PlaintextPasswordHasher()}))
    credentials.add_subscriber(CheckCredentialsListener(hasher, PlaintextPasswordHasher()))
    manager = AuthenticatorManager([json_login], TokenStorage(), credentials, "api")
    firewall_map = FirewallMap(
        [
            (
                PathRequestMatcher("^/"),
                FakeFirewallContext(
                    name="api",
                    authenticator_manager=manager,
                    access_listener=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type] -- the chain never asks the context for it
                    listeners=(AuthenticatorManagerListener(manager, StarletteHttpFactory()),),
                ),
            ),
        ],
    )
    dispatcher = EventDispatcher()
    dispatcher.add_subscriber(Firewall(firewall_map))
    routes = [Route("/api/login", _echo_body, methods=["POST"])]
    return RequestLifecycleMiddleware(
        Starlette(routes=routes), dispatcher=dispatcher, message_factory=message_factory()
    )


def _document(password: str) -> bytes:
    """Return the JSON document a client logs ``alice`` in with, under ``password``."""
    return json.dumps({"username": "alice", "password": password}).encode()


async def test_a_json_login_posted_as_its_body_is_answered_by_the_success_handler() -> None:
    status, _headers, content = await send(
        _application(_NamingSuccess()),
        "POST",
        "/api/login",
        _document("secret"),
        content_type=_JSON,
    )

    assert status == 200
    assert content == b"logged in alice"


async def test_a_wrong_password_posted_as_the_body_is_answered_with_a_401() -> None:
    status, _headers, content = await send(
        _application(_NamingSuccess()),
        "POST",
        "/api/login",
        _document("wrong"),
        content_type=_JSON,
    )

    assert status == 401
    assert json.loads(content) == {"error": "The presented credentials are invalid."}


async def test_the_route_still_reads_the_raw_body_after_the_login() -> None:
    document = _document("secret")

    status, _headers, content = await send(
        _application(_ContinuingSuccess()),
        "POST",
        "/api/login",
        document,
        content_type=_JSON,
    )

    assert status == 200
    assert content == b"route read " + document
