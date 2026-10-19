"""The login-link authenticator: a followed link spent into a login."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.exception import AuthenticationError, InvalidArgumentError
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.login_link import RecordingLoginLinkHandler
from tests.support.messages import make_message
from xtr_security_http.authenticator.debug.unsupported_reasons import UnsupportedReasons
from xtr_security_http.authenticator.fallback_user_loader import FallbackUserLoader
from xtr_security_http.authenticator.login_link_authenticator import LoginLinkAuthenticator
from xtr_security_http.authenticator.passport.badge.remember_me_badge import RememberMeBadge
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.self_validating_passport import (
    SelfValidatingPassport,
)
from xtr_security_http.authenticator.token.post_authentication_token import (
    PostAuthenticationToken,
)
from xtr_security_http.exception import (
    InvalidLoginLinkAuthenticationError,
    InvalidLoginLinkError,
)
from xtr_security_http.http_utils import HttpUtils
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

pytestmark = pytest.mark.anyio


@final
class _Success:
    """A success handler that answers with a fixed response."""

    def __init__(self) -> None:
        self.tokens: list[object] = []

    async def on_authentication_success(
        self,
        request: ServerRequestInterface,
        token: object,
    ) -> ResponseInterface | None:
        """Record the token, and answer with a response of the handler's own."""
        del request
        self.tokens.append(token)
        return ResponseFactory().create_response(200)


@final
class _Failure:
    """A failure handler that answers with a fixed response."""

    def __init__(self) -> None:
        self.errors: list[AuthenticationError] = []

    async def on_authentication_failure(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface:
        """Record the error, and answer with a response of the handler's own."""
        del request
        self.errors.append(error)
        return ResponseFactory().create_response(401)


def _authenticator(
    handler: RecordingLoginLinkHandler,
    *,
    options: dict[str, object] | None = None,
) -> tuple[LoginLinkAuthenticator, _Success, _Failure]:
    """Build the authenticator over the handler, its answers recorded."""
    success = _Success()
    failure = _Failure()
    authenticator = LoginLinkAuthenticator(
        handler,
        HttpUtils(ResponseFactory()),
        success,
        failure,
        {"check_path": "/login-link", **(options or {})},
    )
    return authenticator, success, failure


def _request(
    query: str = "",
    *,
    method: str = "GET",
    parsed_body: object = None,
    reasons: UnsupportedReasons | None = None,
) -> ServerRequestInterface:
    """Build a request arriving at the check path, shaped as asked."""
    message = make_message(method=method, path="/login-link", query=query, parsed_body=parsed_body)
    if reasons is not None:
        message = message.with_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS, reasons)
    return message


def _off_path(reasons: UnsupportedReasons) -> ServerRequestInterface:
    """Build a request arriving somewhere other than the check path."""
    message = make_message(path="/")
    return message.with_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS, reasons)


def test_the_authenticator_requires_a_check_path_option() -> None:
    with pytest.raises(InvalidArgumentError, match="requires a check_path option"):
        _ = LoginLinkAuthenticator(
            RecordingLoginLinkHandler(),
            HttpUtils(ResponseFactory()),
            _Success(),
            _Failure(),
            {},
        )


def test_the_authenticator_refuses_a_check_route_option() -> None:
    with pytest.raises(InvalidArgumentError, match='"check_route" option is not supported'):
        _ = LoginLinkAuthenticator(
            RecordingLoginLinkHandler(),
            HttpUtils(ResponseFactory()),
            _Success(),
            _Failure(),
            {"check_path": "/login-link", "check_route": "app_login_link"},
        )


def test_supports_handles_the_request_that_arrives_at_the_check_path() -> None:
    authenticator, _success, _failure = _authenticator(RecordingLoginLinkHandler())

    assert authenticator.supports(_request()) is True


def test_supports_refuses_a_method_the_post_only_option_rejects() -> None:
    authenticator, _success, _failure = _authenticator(
        RecordingLoginLinkHandler(),
        options={"check_post_only": True},
    )
    reasons = UnsupportedReasons()

    assert authenticator.supports(_request(reasons=reasons)) is False
    assert reasons.all() == (
        'the request method is "GET", and the "check_post_only" option requires POST',
    )


def test_supports_refuses_a_request_off_the_check_path() -> None:
    authenticator, _success, _failure = _authenticator(RecordingLoginLinkHandler())
    reasons = UnsupportedReasons()

    assert authenticator.supports(_off_path(reasons)) is False
    assert reasons.all() == (
        'the request path "/" does not match the "check_path" option "/login-link"',
    )


async def test_authenticate_refuses_a_request_with_no_user_parameter() -> None:
    authenticator, _success, _failure = _authenticator(RecordingLoginLinkHandler())

    with pytest.raises(InvalidLoginLinkAuthenticationError, match="Missing user from link"):
        _ = await authenticator.authenticate(_request())


async def test_authenticate_reads_the_user_from_the_query() -> None:
    user = InMemoryUser("ada")
    handler = RecordingLoginLinkHandler(user)
    authenticator, _success, _failure = _authenticator(handler)

    passport = await authenticator.authenticate(_request("user=ada"))

    badge = passport.get_badge(UserBadge)
    assert badge is not None
    assert badge.get_user_identifier() == "ada"


async def test_authenticate_reads_the_user_from_the_body_of_a_post() -> None:
    user = InMemoryUser("ada")
    handler = RecordingLoginLinkHandler(user)
    authenticator, _success, _failure = _authenticator(handler)

    passport = await authenticator.authenticate(
        _request(method="POST", parsed_body={"user": "ada"}),
    )

    badge = passport.get_badge(UserBadge)
    assert badge is not None
    assert badge.get_user_identifier() == "ada"


async def test_authenticate_does_not_read_the_body_of_a_get() -> None:
    authenticator, _success, _failure = _authenticator(RecordingLoginLinkHandler())

    with pytest.raises(InvalidLoginLinkAuthenticationError, match="Missing user from link"):
        _ = await authenticator.authenticate(
            _request(method="GET", parsed_body={"user": "ada"}),
        )


async def test_the_passport_validates_itself_around_the_spent_link() -> None:
    user = InMemoryUser("ada")
    handler = RecordingLoginLinkHandler(user)
    authenticator, _success, _failure = _authenticator(handler)
    request = _request("user=ada")

    passport = await authenticator.authenticate(request)

    assert isinstance(passport, SelfValidatingPassport)
    assert await passport.get_user() is user
    assert handler.consumed == [request]


async def test_the_badge_keeps_its_own_loader() -> None:
    user = InMemoryUser("ada")
    authenticator, _success, _failure = _authenticator(RecordingLoginLinkHandler(user))

    passport = await authenticator.authenticate(_request("user=ada"))

    badge = passport.get_badge(UserBadge)
    assert badge is not None
    assert isinstance(badge.get_user_loader(), FallbackUserLoader)


async def test_the_passport_wears_the_remember_me_badge() -> None:
    user = InMemoryUser("ada")
    authenticator, _success, _failure = _authenticator(RecordingLoginLinkHandler(user))

    passport = await authenticator.authenticate(_request("user=ada"))

    assert passport.get_badge(RememberMeBadge) is not None


async def test_a_refused_link_becomes_the_authentication_error_of_the_flow() -> None:
    refused = InvalidLoginLinkError('Missing "hash" parameter.')
    handler = RecordingLoginLinkHandler(error=refused)
    authenticator, _success, _failure = _authenticator(handler)

    passport = await authenticator.authenticate(_request("user=ada"))

    with pytest.raises(InvalidLoginLinkAuthenticationError) as raised:
        _ = await passport.get_user()
    assert str(raised.value) == "Login link could not be validated."
    assert raised.value.__cause__ is refused


async def test_create_token_mints_a_post_authentication_token() -> None:
    user = InMemoryUser("ada", roles=("ROLE_USER",))
    handler = RecordingLoginLinkHandler(user)
    authenticator, _success, _failure = _authenticator(handler)
    passport = await authenticator.authenticate(_request("user=ada"))

    token = await authenticator.create_token(passport, "main")

    assert isinstance(token, PostAuthenticationToken)
    assert token.get_user_identifier() == "ada"
    assert token.get_firewall_name() == "main"


async def test_a_successful_login_delegates_to_the_success_handler() -> None:
    authenticator, success, _failure = _authenticator(RecordingLoginLinkHandler())
    token = NullToken()

    response = await authenticator.on_authentication_success(_request(), token, "main")

    assert response is not None
    assert response.get_status_code() == 200
    assert success.tokens == [token]


async def test_a_failed_login_delegates_to_the_failure_handler() -> None:
    authenticator, _success, failure = _authenticator(RecordingLoginLinkHandler())
    error = InvalidLoginLinkAuthenticationError("Login link could not be validated.")

    response = await authenticator.on_authentication_failure(_request(), error)

    assert response.get_status_code() == 401
    assert failure.errors == [error]


def test_the_login_is_the_users_own_act() -> None:
    authenticator, _success, _failure = _authenticator(RecordingLoginLinkHandler())

    assert authenticator.is_interactive() is True
