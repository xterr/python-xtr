"""The default failure answer: back to the login page, the error kept for the form."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_http_foundation import MemorySessionStorage, Session
from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core.exception import BadCredentialsError, InvalidArgumentError

from tests.support.messages import make_message
from xtr_security_http._security_state import security_state_of
from xtr_security_http.authentication.default_authentication_failure_handler import (
    DefaultAuthenticationFailureHandler,
)
from xtr_security_http.http_utils import HttpUtils
from xtr_security_http.security_request_attributes import SecurityRequestAttributes
from xtr_security_http.util import get_target_path

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

pytestmark = pytest.mark.anyio


def _handler(
    options: dict[str, object] | None = None,
    *,
    firewall_name: str | None = None,
) -> DefaultAuthenticationFailureHandler:
    """Build the handler over the real URI machinery."""
    return DefaultAuthenticationFailureHandler(
        HttpUtils(ResponseFactory()),
        options,
        firewall_name=firewall_name,
    )


def _request_with_session(
    *,
    method: str = "POST",
    path: str = "/login_check",
    query: str = "",
    referer: str | None = None,
) -> tuple[ServerRequestInterface, Session]:
    """Build a request whose security state carries a parked session."""
    bag: dict[str, object] = {}
    headers = {} if referer is None else {"Referer": referer}
    message = make_message(
        method=method,
        path=path,
        query=query,
        headers=headers,
    ).with_attribute(SecurityRequestAttributes.STATE_BAG, bag)
    session = Session(MemorySessionStorage())
    security_state_of(bag).attributes[SecurityRequestAttributes.SESSION] = session
    return message, session


async def test_a_failure_redirects_to_the_login_page_and_keeps_the_error() -> None:
    message, session = _request_with_session()
    error = BadCredentialsError("failed")

    response = await _handler().on_authentication_failure(message, error)

    assert response.get_status_code() == 302
    assert response.get_header_line("Location") == "/login"
    kept = await session.get(SecurityRequestAttributes.AUTHENTICATION_ERROR)
    assert kept is error


async def test_a_configured_failure_path_wins_over_the_login_page() -> None:
    message, _session = _request_with_session()

    response = await _handler({"failure_path": "/failed"}).on_authentication_failure(
        message,
        BadCredentialsError("failed"),
    )

    assert response.get_header_line("Location") == "/failed"


async def test_a_path_the_request_carried_under_the_configured_parameter_wins() -> None:
    message, _session = _request_with_session(query="_failure_path=/carried")

    response = await _handler({"failure_path": "/failed"}).on_authentication_failure(
        message,
        BadCredentialsError("failed"),
    )

    assert response.get_header_line("Location") == "/carried"


async def test_a_carried_path_that_is_no_path_is_ignored() -> None:
    message, _session = _request_with_session(query="_failure_path=not-a-path")

    response = await _handler({"failure_path": "/failed"}).on_authentication_failure(
        message,
        BadCredentialsError("failed"),
    )

    assert response.get_header_line("Location") == "/failed"


async def test_a_request_without_a_session_redirects_without_keeping_the_error() -> None:
    message = make_message(method="POST", path="/login_check")

    response = await _handler().on_authentication_failure(message, BadCredentialsError("failed"))

    assert response.get_status_code() == 302
    assert response.get_header_line("Location") == "/login"


async def test_the_forward_option_is_refused() -> None:
    message, _session = _request_with_session()

    with pytest.raises(InvalidArgumentError):
        _ = await _handler({"failure_forward": True}).on_authentication_failure(
            message,
            BadCredentialsError("failed"),
        )


async def test_a_referer_of_the_applications_own_host_is_kept_as_the_target() -> None:
    message, session = _request_with_session(referer="https://example.com/where?asked=1")

    _ = await _handler({"use_referer": True}, firewall_name="main").on_authentication_failure(
        message,
        BadCredentialsError("failed"),
    )

    assert await get_target_path(session, "main") == "https://example.com/where"


async def test_a_referer_of_another_host_is_not_kept() -> None:
    message, session = _request_with_session(referer="https://elsewhere.example/where")

    _ = await _handler({"use_referer": True}, firewall_name="main").on_authentication_failure(
        message,
        BadCredentialsError("failed"),
    )

    assert await get_target_path(session, "main") is None


async def test_a_referer_naming_the_login_page_is_not_kept() -> None:
    message, session = _request_with_session(referer="https://example.com/login")

    _ = await _handler({"use_referer": True}, firewall_name="main").on_authentication_failure(
        message,
        BadCredentialsError("failed"),
    )

    assert await get_target_path(session, "main") is None


async def test_a_referer_naming_the_requested_page_is_not_kept() -> None:
    message, session = _request_with_session(referer="https://example.com/login_check")

    _ = await _handler({"use_referer": True}, firewall_name="main").on_authentication_failure(
        message,
        BadCredentialsError("failed"),
    )

    assert await get_target_path(session, "main") is None


async def test_an_already_kept_target_is_not_overwritten_by_the_referer() -> None:
    message, session = _request_with_session(referer="https://example.com/where")
    await session.set(SecurityRequestAttributes.TARGET_PATH.format(firewall="main"), "/kept")

    _ = await _handler({"use_referer": True}, firewall_name="main").on_authentication_failure(
        message,
        BadCredentialsError("failed"),
    )

    assert await get_target_path(session, "main") == "/kept"


async def test_the_referer_is_not_kept_without_a_firewall_name() -> None:
    message, session = _request_with_session(referer="https://example.com/where")

    _ = await _handler({"use_referer": True}).on_authentication_failure(
        message, BadCredentialsError("failed")
    )

    assert await get_target_path(session, "main") is None


async def test_the_referer_is_not_kept_when_the_default_target_always_wins() -> None:
    message, session = _request_with_session(referer="https://example.com/where")

    _ = await _handler(
        {"use_referer": True, "always_use_default_target_path": True},
        firewall_name="main",
    ).on_authentication_failure(message, BadCredentialsError("failed"))

    assert await get_target_path(session, "main") is None


def test_the_options_merge_over_the_defaults() -> None:
    handler = _handler({"login_path": "/sign-in"})

    assert handler.get_options()["login_path"] == "/sign-in"
    assert handler.get_options()["failure_path"] is None

    handler.set_options({"failure_path": "/failed"})
    assert handler.get_options()["login_path"] == "/login"
    assert handler.get_options()["failure_path"] == "/failed"
