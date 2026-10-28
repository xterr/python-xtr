"""The default success answer: back where the caller was heading."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_http_foundation import MemorySessionStorage, Session
from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core.authentication.token.null_token import NullToken

from tests.support.messages import make_message
from xtr_security_http._security_state import security_state_of
from xtr_security_http.authentication.default_authentication_success_handler import (
    DefaultAuthenticationSuccessHandler,
)
from xtr_security_http.http_utils import HttpUtils
from xtr_security_http.security_request_attributes import SecurityRequestAttributes
from xtr_security_http.util import get_target_path

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

pytestmark = pytest.mark.anyio


def _handler(**options: object) -> DefaultAuthenticationSuccessHandler:
    """Build the handler over the real URI machinery."""
    return DefaultAuthenticationSuccessHandler(HttpUtils(ResponseFactory()), options)


def _request_with_session(
    *,
    path: str = "/",
    query: str = "",
    referer: str | None = None,
) -> tuple[ServerRequestInterface, Session]:
    """Build a request whose security state carries a parked session."""
    bag: dict[str, object] = {}
    headers = {} if referer is None else {"Referer": referer}
    message = make_message(path=path, query=query, headers=headers).with_attribute(
        SecurityRequestAttributes.STATE_BAG,
        bag,
    )
    session = Session(MemorySessionStorage())
    security_state_of(bag).attributes[SecurityRequestAttributes.SESSION] = session
    return message, session


async def test_a_success_redirects_to_the_default_target() -> None:
    message, _session = _request_with_session()

    response = await _handler().on_authentication_success(message, NullToken())

    assert response is not None
    assert response.get_status_code() == 302
    assert response.get_header_line("Location") == "/"


async def test_the_default_target_always_wins_when_the_option_says_so() -> None:
    message, _session = _request_with_session(query="_target_path=/carried")

    response = await _handler(
        always_use_default_target_path=True, default_target_path="/home"
    ).on_authentication_success(
        message,
        NullToken(),
    )

    assert response is not None
    assert response.get_header_line("Location") == "/home"


async def test_a_path_the_request_carried_under_the_configured_parameter_wins() -> None:
    message, _session = _request_with_session(query="_target_path=/carried")

    response = await _handler().on_authentication_success(message, NullToken())

    assert response is not None
    assert response.get_header_line("Location") == "/carried"


async def test_a_carried_path_that_is_no_path_is_ignored() -> None:
    message, _session = _request_with_session(query="_target_path=not-a-path")

    response = await _handler().on_authentication_success(message, NullToken())

    assert response is not None
    assert response.get_header_line("Location") == "/"


async def test_the_target_the_interrupted_request_saved_wins_and_is_removed() -> None:
    message, session = _request_with_session()
    await session.set(SecurityRequestAttributes.TARGET_PATH.format(firewall="main"), "/kept")
    handler = _handler()
    handler.set_firewall_name("main")

    response = await handler.on_authentication_success(message, NullToken())

    assert response is not None
    assert response.get_header_line("Location") == "/kept"
    assert await get_target_path(session, "main") is None


async def test_no_saved_target_without_a_firewall_name() -> None:
    message, session = _request_with_session()
    await session.set(SecurityRequestAttributes.TARGET_PATH.format(firewall="main"), "/kept")

    response = await _handler().on_authentication_success(message, NullToken())

    assert response is not None
    assert response.get_header_line("Location") == "/"
    assert await get_target_path(session, "main") == "/kept"


async def test_the_referer_wins_when_the_option_asks_for_it() -> None:
    message, _session = _request_with_session(referer="https://example.com/where?asked=1")

    response = await _handler(use_referer=True).on_authentication_success(message, NullToken())

    assert response is not None
    assert response.get_header_line("Location") == "https://example.com/where"


async def test_a_referer_naming_the_login_page_is_ignored() -> None:
    message, _session = _request_with_session(referer="https://example.com/login")

    response = await _handler(use_referer=True).on_authentication_success(message, NullToken())

    assert response is not None
    assert response.get_header_line("Location") == "/"


async def test_a_referer_naming_the_requested_page_is_ignored() -> None:
    message, _session = _request_with_session(path="/here", referer="https://example.com/here")

    response = await _handler(use_referer=True).on_authentication_success(message, NullToken())

    assert response is not None
    assert response.get_header_line("Location") == "/"


def test_the_options_and_the_firewalls_name_are_set_and_read() -> None:
    handler = _handler(default_target_path="/home")

    assert handler.get_options()["default_target_path"] == "/home"
    assert handler.get_firewall_name() is None

    handler.set_options({"default_target_path": "/"})
    handler.set_firewall_name("api")

    assert handler.get_options()["default_target_path"] == "/"
    assert handler.get_firewall_name() == "api"
