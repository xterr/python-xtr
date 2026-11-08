"""A form login served the way a browser submits one: a POST carrying the form as its body.

The request goes through the kernel's lifecycle middleware, so the chain is
handed the request the kernel serves — connected to its wire, the body unread
— and the real manager runs the real form login over it, its credentials
checked by the real credentials listener.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from typing_extensions import override
from xtr_event_dispatcher import EventDispatcher
from xtr_http_foundation import MemorySessionStorage, PathRequestMatcher, Session
from xtr_http_kernel import RequestLifecycleMiddleware
from xtr_http_kernel.bridge import ResponseFactory, StarletteHttpFactory
from xtr_password_hasher import PasswordHasherFactory, PlaintextPasswordHasher, UserPasswordHasher
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.user import InMemoryUser

from tests.support.contexts import FakeFirewallContext
from tests.support.served import BodyChannel, http_scope, message_factory
from xtr_security_http._security_state import security_state_of
from xtr_security_http.authentication.authenticator_manager import AuthenticatorManager
from xtr_security_http.authentication.default_authentication_failure_handler import (
    DefaultAuthenticationFailureHandler,
)
from xtr_security_http.authentication.default_authentication_success_handler import (
    DefaultAuthenticationSuccessHandler,
)
from xtr_security_http.authenticator.form_login_authenticator import FormLoginAuthenticator
from xtr_security_http.event_listener.check_credentials_listener import CheckCredentialsListener
from xtr_security_http.firewall.abstract_listener import AbstractListener
from xtr_security_http.firewall.authenticator_manager_listener import (
    AuthenticatorManagerListener,
)
from xtr_security_http.firewall.firewall import Firewall
from xtr_security_http.firewall_map import FirewallMap
from xtr_security_http.http_utils import HttpUtils
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.types import ASGIApp, Message
    from xtr_http_kernel import RequestEvent
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface

    from xtr_security_http.authentication.authentication_success_handler_interface import (
        AuthenticationSuccessHandlerInterface,
    )

pytestmark = pytest.mark.anyio

_FORM = "application/x-www-form-urlencoded"


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
class _ContinuingSuccess:
    """Lets the request go on to its route after the login."""

    async def on_authentication_success(
        self, request: ServerRequestInterface, token: TokenInterface
    ) -> ResponseInterface | None:
        del request, token
        return None


@final
class _SessionStep(AbstractListener):
    """Parks a session on the request's state, the way the context step does."""

    @override
    async def supports(self, request: ServerRequestInterface) -> bool | None:
        return True

    @override
    async def authenticate(self, request_event: RequestEvent) -> None:
        security_state_of(request_event.state).attributes[SecurityRequestAttributes.SESSION] = (
            Session(MemorySessionStorage())
        )


async def _echo_username(request: Request) -> PlainTextResponse:
    """Answer with the username the route itself reads out of the posted form."""
    form = await request.form()
    return PlainTextResponse(f"route read {form.get('_username')}")


def _application(
    success_handler: AuthenticationSuccessHandlerInterface,
    options: dict[str, object] | None = None,
) -> ASGIApp:
    """Return an application whose one firewall logs in through a real form login."""
    http_utils = HttpUtils(ResponseFactory())
    form_login = FormLoginAuthenticator(
        http_utils,
        _Users(),
        success_handler,
        DefaultAuthenticationFailureHandler(http_utils, {"login_path": "/login"}),
        {"login_path": "/login", **(options or {})},
    )
    credentials = EventDispatcher()
    hasher = UserPasswordHasher(PasswordHasherFactory({InMemoryUser: PlaintextPasswordHasher()}))
    credentials.add_subscriber(CheckCredentialsListener(hasher, PlaintextPasswordHasher()))
    manager = AuthenticatorManager([form_login], TokenStorage(), credentials, "main")
    firewall_map = FirewallMap(
        [
            (
                PathRequestMatcher("^/"),
                FakeFirewallContext(
                    name="main",
                    authenticator_manager=manager,
                    access_listener=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
                    listeners=(
                        _SessionStep(),
                        AuthenticatorManagerListener(manager, StarletteHttpFactory()),
                    ),
                ),
            ),
        ],
    )
    dispatcher = EventDispatcher()
    dispatcher.add_subscriber(Firewall(firewall_map))
    routes = [Route("/login_check", _echo_username, methods=["GET", "POST"])]
    return RequestLifecycleMiddleware(
        Starlette(routes=routes), dispatcher=dispatcher, message_factory=message_factory()
    )


async def _send(  # noqa: PLR0913 -- a test client, naming every part of the request it sends
    app: ASGIApp,
    method: str,
    path: str,
    body: bytes = b"",
    *,
    query: str = "",
    content_type: str | None = None,
) -> tuple[int, dict[str, str], bytes]:
    """Send one request straight at ``app``, answering its status, headers and body."""
    sent: list[Message] = []

    async def send(message: Message) -> None:
        sent.append(message)

    scope = http_scope(method, path, query=query, content_type=content_type)
    await app(scope, BodyChannel(body), send)
    start = sent[0]
    headers = {
        name.decode(): value.decode()
        for name, value in cast("list[tuple[bytes, bytes]]", start["headers"])
    }
    content = b"".join(
        cast("bytes", message.get("body", b""))
        for message in sent
        if message["type"] == "http.response.body"
    )
    return cast("int", start["status"]), headers, content


def _redirecting() -> DefaultAuthenticationSuccessHandler:
    return DefaultAuthenticationSuccessHandler(
        HttpUtils(ResponseFactory()), {"default_target_path": "/home"}
    )


async def test_a_login_form_posted_as_its_body_logs_the_user_in() -> None:
    status, headers, _content = await _send(
        _application(_redirecting()),
        "POST",
        "/login_check",
        b"_username=alice&_password=secret&_target_path=%2Fafter",
        content_type=_FORM,
    )

    assert status == 302
    assert headers["location"] == "/after"


async def test_a_posted_target_on_another_origin_lands_on_the_default_target() -> None:
    status, headers, _content = await _send(
        _application(_redirecting()),
        "POST",
        "/login_check",
        b"_username=alice&_password=secret&_target_path=https%3A%2F%2Fevil.example%2F",
        content_type=_FORM,
    )

    assert status == 302
    assert headers["location"] == "/home"


async def test_a_wrong_password_posted_as_the_body_returns_to_the_login_page() -> None:
    status, headers, _content = await _send(
        _application(_redirecting()),
        "POST",
        "/login_check",
        b"_username=alice&_password=wrong",
        content_type=_FORM,
    )

    assert status == 302
    assert headers["location"] == "/login"


async def test_the_route_still_reads_the_posted_form_after_the_login() -> None:
    status, _headers, content = await _send(
        _application(_ContinuingSuccess()),
        "POST",
        "/login_check",
        b"_username=alice&_password=secret",
        content_type=_FORM,
    )

    assert status == 200
    assert content == b"route read alice"


async def test_a_login_in_the_query_string_still_logs_in_once_post_only_is_off() -> None:
    status, headers, _content = await _send(
        _application(_redirecting(), {"post_only": False}),
        "GET",
        "/login_check",
        query="_username=alice&_password=secret&_target_path=%2Fafter",
    )

    assert status == 302
    assert headers["location"] == "/after"
