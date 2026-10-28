"""The base every form-login authenticator shares."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override
from xtr_http_foundation import MemorySessionStorage, Session
from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core.exception import BadCredentialsError

from tests.support.messages import make_message
from xtr_security_http._security_state import security_state_of
from xtr_security_http.authenticator.abstract_login_form_authenticator import (
    AbstractLoginFormAuthenticator,
)
from xtr_security_http.authenticator.debug.unsupported_reasons import UnsupportedReasons
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.self_validating_passport import SelfValidatingPassport
from xtr_security_http.http_utils import HttpUtils
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_http.authenticator.passport.passport import Passport

pytestmark = pytest.mark.anyio


@final
class _Login(AbstractLoginFormAuthenticator):
    """A form-login authenticator naming a fixed login page."""

    def __init__(self) -> None:
        super().__init__(HttpUtils(ResponseFactory()))

    @override
    def get_login_url(self, request: ServerRequestInterface) -> str:
        del request
        return "/login"

    @override
    async def authenticate(self, request: ServerRequestInterface) -> Passport:
        """Hand back a self-validating passport; the tests never reach this."""
        del request
        return SelfValidatingPassport(UserBadge("alice"))


def _authenticator() -> AbstractLoginFormAuthenticator:
    return _Login()


def _request_with_session(
    *,
    method: str = "POST",
    path: str = "/login",
) -> tuple[ServerRequestInterface, Session]:
    """Build a request whose security state carries a parked session."""
    bag: dict[str, object] = {}
    message = make_message(method=method, path=path).with_attribute(
        SecurityRequestAttributes.STATE_BAG,
        bag,
    )
    session = Session(MemorySessionStorage())
    security_state_of(bag).attributes[SecurityRequestAttributes.SESSION] = session
    return message, session


def test_the_form_submission_is_supported() -> None:
    message, _session = _request_with_session()

    assert _authenticator().supports(message) is True


def test_a_get_request_is_refused_with_a_reason() -> None:
    message, _session = _request_with_session(method="GET")
    reasons = UnsupportedReasons()
    asked = message.with_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS, reasons)

    assert _authenticator().supports(asked) is False
    assert reasons.all() == ('the request method is "GET", and only POST is supported',)


def test_a_request_off_the_login_page_is_refused_with_a_reason() -> None:
    message, _session = _request_with_session(path="/elsewhere")
    reasons = UnsupportedReasons()
    asked = message.with_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS, reasons)

    assert _authenticator().supports(asked) is False
    assert reasons.all() == ('the request path "/elsewhere" does not match the login URL "/login"',)


async def test_a_failed_login_keeps_the_error_and_redirects_to_the_login_page() -> None:
    message, session = _request_with_session()
    error = BadCredentialsError("failed")

    response = await _authenticator().on_authentication_failure(message, error)

    assert response is not None
    assert response.get_status_code() == 302
    assert response.get_header_line("Location") == "/login"
    kept = await session.get(SecurityRequestAttributes.AUTHENTICATION_ERROR)
    assert kept is error


async def test_a_failed_login_without_a_session_redirects_without_keeping_the_error() -> None:
    message = make_message(method="POST", path="/login")

    response = await _authenticator().on_authentication_failure(message, BadCredentialsError("x"))

    assert response is not None
    assert response.get_header_line("Location") == "/login"


async def test_the_entry_point_redirects_to_the_login_page() -> None:
    message = make_message()

    response = await _authenticator().start(message, BadCredentialsError("reached protected"))

    assert response.get_status_code() == 302
    assert response.get_header_line("Location") == "/login"


def test_the_login_is_the_users_own_act() -> None:
    assert _authenticator().is_interactive() is True


def test_the_login_url_stays_abstract() -> None:
    class _Bare(AbstractLoginFormAuthenticator):
        """A subclass that implements nothing of its own."""

        @override
        async def authenticate(self, request: ServerRequestInterface) -> Passport:
            """Hand back a self-validating passport; the test never reaches this."""
            del request
            return SelfValidatingPassport(UserBadge("alice"))

    with pytest.raises(NotImplementedError):
        _ = _Bare(HttpUtils(ResponseFactory())).get_login_url(make_message())
