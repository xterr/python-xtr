"""The default failure answer: back to the login page, the error kept for the form."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from urllib.parse import urlencode

import pytest
from xtr_http_foundation import MemorySessionStorage, Session
from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core.exception import BadCredentialsError, InvalidArgumentError

from tests.support.messages import make_message
from tests.support.served import served_message
from xtr_security_http._security_state import security_state_of
from xtr_security_http.authentication.default_authentication_failure_handler import (
    DefaultAuthenticationFailureHandler,
)
from xtr_security_http.http_utils import HttpUtils
from xtr_security_http.security_request_attributes import SecurityRequestAttributes
from xtr_security_http.session.authentication_error_serializer import (
    authentication_error_to_session,
)
from xtr_security_http.util import get_target_path

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

    from tests.support.served import BodyChannel

pytestmark = pytest.mark.anyio

_FORM = "application/x-www-form-urlencoded"


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
    parsed_body: object | None = None,
) -> tuple[ServerRequestInterface, Session]:
    """Build a request whose security state carries a parked session."""
    bag: dict[str, object] = {}
    headers = {} if referer is None else {"Referer": referer}
    message = make_message(
        method=method,
        path=path,
        query=query,
        headers=headers,
        parsed_body=parsed_body,
    ).with_attribute(SecurityRequestAttributes.STATE_BAG, bag)
    session = Session(MemorySessionStorage())
    security_state_of(bag).attributes[SecurityRequestAttributes.SESSION] = session
    return message, session


def _served_with_session(
    body: bytes,
    content_type: str,
) -> tuple[ServerRequestInterface, BodyChannel]:
    """Serve a login POST the kernel's way, its security state carrying a parked session."""
    served, channel = served_message("POST", "/login_check", body, content_type=content_type)
    bag: dict[str, object] = {}
    security_state_of(bag).attributes[SecurityRequestAttributes.SESSION] = Session(
        MemorySessionStorage()
    )
    return served.with_attribute(SecurityRequestAttributes.STATE_BAG, bag), channel


async def test_a_failure_redirects_to_the_login_page_and_keeps_the_error() -> None:
    message, session = _request_with_session()
    error = BadCredentialsError("failed")

    response = await _handler().on_authentication_failure(message, error)

    assert response.get_status_code() == 302
    assert response.get_header_line("Location") == "/login"
    kept = await session.get(SecurityRequestAttributes.AUTHENTICATION_ERROR)
    assert kept == authentication_error_to_session(error)


async def test_the_kept_error_is_json_without_its_internal_message() -> None:
    message, session = _request_with_session()
    error = BadCredentialsError("the password of ada did not match")

    _ = await _handler().on_authentication_failure(message, error)

    kept = await session.get(SecurityRequestAttributes.AUTHENTICATION_ERROR)
    assert isinstance(kept, dict)
    assert json.loads(json.dumps(kept)) == kept
    assert "the password of ada" not in json.dumps(kept)


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


@pytest.mark.parametrize(
    "target",
    [
        "https://evil.example/after",
        "//evil.example/after",
        "/\\evil.example/after",
        "https://evil.example\\@example.com/after",
    ],
)
async def test_a_carried_path_on_another_origin_is_ignored(target: str) -> None:
    message, _session = _request_with_session(query=urlencode({"_failure_path": target}))

    response = await _handler({"failure_path": "/failed"}).on_authentication_failure(
        message,
        BadCredentialsError("failed"),
    )

    assert response.get_header_line("Location") == "/failed"


async def test_a_posted_path_on_another_origin_is_ignored() -> None:
    message, _session = _request_with_session(
        parsed_body={"_failure_path": "https://evil.example/after"},
    )

    response = await _handler({"failure_path": "/failed"}).on_authentication_failure(
        message,
        BadCredentialsError("failed"),
    )

    assert response.get_header_line("Location") == "/failed"


async def test_a_path_posted_in_a_served_form_wins() -> None:
    message, _channel = _served_with_session(b"_failure_path=%2Fcarried", _FORM)

    response = await _handler({"failure_path": "/failed"}).on_authentication_failure(
        message,
        BadCredentialsError("failed"),
    )

    assert response.get_header_line("Location") == "/carried"


async def test_a_served_body_that_is_no_form_is_not_read_for_the_failure_path() -> None:
    message, channel = _served_with_session(b"_failure_path=%2Fcarried", "application/octet-stream")

    response = await _handler({"failure_path": "/failed"}).on_authentication_failure(
        message,
        BadCredentialsError("failed"),
    )

    assert response.get_header_line("Location") == "/failed"
    assert channel.reads == 0


async def test_a_carried_absolute_url_on_the_requests_own_origin_wins() -> None:
    message, _session = _request_with_session(
        query=urlencode({"_failure_path": "https://example.com/carried"}),
    )

    response = await _handler({"failure_path": "/failed"}).on_authentication_failure(
        message,
        BadCredentialsError("failed"),
    )

    assert response.get_header_line("Location") == "https://example.com/carried"


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
