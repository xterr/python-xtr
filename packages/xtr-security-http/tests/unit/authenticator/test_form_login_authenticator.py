"""The form-login authenticator: a username and a password out of a submitted form."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import pytest
from xtr_http_foundation import MemorySessionStorage, Session
from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.authentication.token.username_password_token import UsernamePasswordToken
from xtr_security_core.exception import (
    AuthenticationError,
    BadCredentialsError,
    InvalidArgumentError,
)
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.messages import make_message
from xtr_security_http._security_state import security_state_of
from xtr_security_http.authenticator.debug.unsupported_reasons import UnsupportedReasons
from xtr_security_http.authenticator.form_login_authenticator import FormLoginAuthenticator
from xtr_security_http.authenticator.passport.badge.csrf_token_badge import CsrfTokenBadge
from xtr_security_http.authenticator.passport.badge.password_upgrade_badge import (
    PasswordUpgradeBadge,
)
from xtr_security_http.authenticator.passport.badge.remember_me_badge import RememberMeBadge
from xtr_security_http.http_utils import HttpUtils
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.user.password_authenticated_user_interface import (
        PasswordAuthenticatedUserInterface,
    )
    from xtr_security_core.user.user_interface import UserInterface

#: A password a test user carries; a fixture, not a secret.
_HASHED = "hashed"

pytestmark = pytest.mark.anyio


class _Provider:
    """A user provider that hands back a user for any identifier."""

    async def load_user_by_identifier(self, identifier: str) -> UserInterface:
        """Hand back an enabled user carrying the identifier."""
        return InMemoryUser(identifier, password=_HASHED, roles=("ROLE_USER",))

    async def refresh_user(self, user: UserInterface) -> UserInterface:
        """Hand the user back as it is; the test never reaches this."""
        return user

    def supports_class(self, user_class: type) -> bool:
        """Answer yes; the test never reaches this."""
        del user_class
        return True


@final
class _NonUpgradingProvider(_Provider):
    """A provider that hands back users, and nothing more."""


@final
class _UpgradingProvider(_Provider):
    """A provider that also accepts password upgrades."""

    async def upgrade_password(
        self,
        user: PasswordAuthenticatedUserInterface,
        new_hashed_password: str,
    ) -> None:
        """Accept the upgrade; the test never reaches it."""
        del user, new_hashed_password


def _provider(*, upgrader: bool = False) -> _Provider:
    """Return a provider that upgrades passwords when asked for one that does."""
    return _UpgradingProvider() if upgrader else _NonUpgradingProvider()


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
    *,
    upgrader: bool = False,
    options: dict[str, object] | None = None,
) -> tuple[FormLoginAuthenticator, _Success, _Failure]:
    success = _Success()
    failure = _Failure()
    authenticator = FormLoginAuthenticator(
        HttpUtils(ResponseFactory()),
        _provider(upgrader=upgrader),
        success,
        failure,
        {"login_path": "/login", **(options or {})},
    )
    return authenticator, success, failure


def _request_with_session(
    *,
    method: str = "POST",
    path: str = "/login_check",
    query: str = "",
    parsed_body: object | None = None,
    content_type: str = "application/x-www-form-urlencoded",
) -> ServerRequestInterface:
    """Build a form submission whose security state carries a parked session."""
    bag: dict[str, object] = {}
    message = make_message(
        method=method,
        path=path,
        query=query,
        headers={"Content-Type": content_type},
        parsed_body=parsed_body,
    ).with_attribute(SecurityRequestAttributes.STATE_BAG, bag)
    security_state_of(bag).attributes[SecurityRequestAttributes.SESSION] = Session(
        MemorySessionStorage(),
    )
    return message


def _session_of(message: ServerRequestInterface) -> Session:
    """Return the session the request's security state carries."""
    bag = message.get_attribute(SecurityRequestAttributes.STATE_BAG)
    assert isinstance(bag, dict)
    session = security_state_of(cast("dict[str, object]", bag)).attributes.get(
        SecurityRequestAttributes.SESSION,
    )
    assert isinstance(session, Session)
    return session


def test_the_authenticator_requires_a_login_path_option() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = FormLoginAuthenticator(
            HttpUtils(ResponseFactory()),
            _Provider(),
            _Success(),
            _Failure(),
            {},
        )


def test_the_login_url_is_generated_from_the_option() -> None:
    authenticator, _success, _failure = _authenticator()

    assert authenticator.get_login_url(make_message()) == "/login"


def test_a_form_submission_is_supported() -> None:
    authenticator, _success, _failure = _authenticator()
    message = _request_with_session(parsed_body={"_username": "alice", "_password": "secret"})

    assert authenticator.supports(message) is True


def test_a_get_request_is_refused_while_post_only_stands() -> None:
    authenticator, _success, _failure = _authenticator()
    reasons = UnsupportedReasons()
    message = _request_with_session(method="GET")
    asked = message.with_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS, reasons)

    assert authenticator.supports(asked) is False
    assert reasons.all() == (
        'the request method is "GET", and the "post_only" option requires POST',
    )


def test_a_get_request_is_supported_once_post_only_is_dropped() -> None:
    authenticator, _success, _failure = _authenticator(options={"post_only": False})
    message = _request_with_session(method="GET")

    assert authenticator.supports(message) is True


def test_a_request_off_the_check_path_is_refused() -> None:
    authenticator, _success, _failure = _authenticator()
    reasons = UnsupportedReasons()
    message = _request_with_session(path="/elsewhere")
    asked = message.with_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS, reasons)

    assert authenticator.supports(asked) is False
    assert reasons.all() == (
        'the request path "/elsewhere" does not match the "check_path" option "/login_check"',
    )


def test_a_non_form_content_type_is_refused_while_form_only_stands() -> None:
    authenticator, _success, _failure = _authenticator(options={"form_only": True})
    reasons = UnsupportedReasons()
    message = _request_with_session(content_type="application/json")
    asked = message.with_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS, reasons)

    assert authenticator.supports(asked) is False


async def test_the_form_reads_into_a_passport() -> None:
    authenticator, _success, _failure = _authenticator()
    message = _request_with_session(parsed_body={"_username": " alice ", "_password": "secret"})

    passport = await authenticator.authenticate(message)

    assert await passport.get_user_badge().get_user() is not None
    assert passport.has_badge(RememberMeBadge)
    assert passport.get_badge(PasswordUpgradeBadge) is None
    assert await _session_of(message).get(SecurityRequestAttributes.LAST_USERNAME) == "alice"


async def test_a_provider_that_upgrades_passwords_earns_the_upgrade_badge() -> None:
    authenticator, _success, _failure = _authenticator(upgrader=True)
    message = _request_with_session(parsed_body={"_username": "alice", "_password": "secret"})

    passport = await authenticator.authenticate(message)

    assert passport.get_badge(PasswordUpgradeBadge) is not None


async def test_an_enabled_csrf_option_adds_the_forgery_badge() -> None:
    authenticator, _success, _failure = _authenticator(options={"enable_csrf": True})
    message = _request_with_session(
        parsed_body={"_username": "alice", "_password": "secret", "_csrf_token": "token"},
    )

    passport = await authenticator.authenticate(message)

    badge = passport.get_badge(CsrfTokenBadge)
    assert badge is not None
    assert badge.get_csrf_token() == "token"
    assert badge.get_csrf_token_id() == "authenticate"


async def test_a_missing_username_fails_the_login() -> None:
    authenticator, _success, _failure = _authenticator()
    message = _request_with_session(parsed_body={"_password": "secret"})

    with pytest.raises(BadCredentialsError):
        _ = await authenticator.authenticate(message)


async def test_an_empty_username_fails_the_login() -> None:
    authenticator, _success, _failure = _authenticator()
    message = _request_with_session(parsed_body={"_username": "  ", "_password": "secret"})

    with pytest.raises(BadCredentialsError):
        _ = await authenticator.authenticate(message)


async def test_a_missing_password_fails_the_login() -> None:
    authenticator, _success, _failure = _authenticator()
    message = _request_with_session(parsed_body={"_username": "alice"})

    with pytest.raises(BadCredentialsError):
        _ = await authenticator.authenticate(message)


async def test_an_empty_password_fails_the_login() -> None:
    authenticator, _success, _failure = _authenticator()
    message = _request_with_session(parsed_body={"_username": "alice", "_password": ""})

    with pytest.raises(BadCredentialsError):
        _ = await authenticator.authenticate(message)


async def test_a_username_that_is_no_string_fails_the_login() -> None:
    authenticator, _success, _failure = _authenticator()
    message = _request_with_session(parsed_body={"_username": ["alice"], "_password": "secret"})

    with pytest.raises(BadCredentialsError):
        _ = await authenticator.authenticate(message)


async def test_a_form_submission_without_a_session_fails_the_login() -> None:
    authenticator, _success, _failure = _authenticator()
    message = make_message(
        method="POST",
        path="/login_check",
        parsed_body={"_username": "alice", "_password": "secret"},
    )

    with pytest.raises(BadCredentialsError):
        _ = await authenticator.authenticate(message)


async def test_the_token_is_a_username_password_one() -> None:
    authenticator, _success, _failure = _authenticator()
    message = _request_with_session(parsed_body={"_username": "alice", "_password": "secret"})
    passport = await authenticator.authenticate(message)

    token = await authenticator.create_token(passport, "main")

    assert isinstance(token, UsernamePasswordToken)
    assert token.get_user_identifier() == "alice"
    assert token.get_firewall_name() == "main"


async def test_a_successful_login_ends_any_re_authentication_and_delegates() -> None:
    authenticator, success, _failure = _authenticator()
    message = _request_with_session()
    await _session_of(message).set(SecurityRequestAttributes.RE_AUTHENTICATION_ATTRIBUTE, "asked")
    token = NullToken()

    response = await authenticator.on_authentication_success(message, token, "main")

    assert response is not None
    assert response.get_status_code() == 200
    assert success.tokens == [token]
    assert (
        await _session_of(message).has(SecurityRequestAttributes.RE_AUTHENTICATION_ATTRIBUTE)
        is False
    )


async def test_a_failed_login_delegates_to_the_failure_handler() -> None:
    authenticator, _success, failure = _authenticator()
    message = _request_with_session()
    error = BadCredentialsError("failed")

    response = await authenticator.on_authentication_failure(message, error)

    assert response.get_status_code() == 401
    assert failure.errors == [error]


async def test_a_re_authentication_keeps_the_identifier_and_the_asked_attribute() -> None:
    authenticator, _success, _failure = _authenticator()
    message = _request_with_session().with_attribute(
        SecurityRequestAttributes.RE_AUTHENTICATION_ATTRIBUTE,
        "ROLE_ADMIN",
    )
    token = NullToken()

    response = await authenticator.start_re_authentication(message, token)

    assert response.get_status_code() == 302
    assert response.get_header_line("Location") == "/login"
    session = _session_of(message)
    assert await session.get(SecurityRequestAttributes.LAST_USERNAME) == ""
    assert await session.get(SecurityRequestAttributes.RE_AUTHENTICATION_ATTRIBUTE) == "ROLE_ADMIN"
