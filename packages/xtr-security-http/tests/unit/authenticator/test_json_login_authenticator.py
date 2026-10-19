"""A stateless login over a JSON document of a username and a password."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core.authentication.token.null_token import NullToken
from xtr_security_core.authentication.token.username_password_token import UsernamePasswordToken
from xtr_security_core.exception import AuthenticationError, BadCredentialsError
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.messages import make_message
from xtr_security_http.authenticator.debug.unsupported_reasons import UnsupportedReasons
from xtr_security_http.authenticator.interactive_authenticator_interface import (
    InteractiveAuthenticatorInterface,
)
from xtr_security_http.authenticator.json_login_authenticator import JsonLoginAuthenticator
from xtr_security_http.authenticator.passport.badge.remember_me_badge import RememberMeBadge
from xtr_security_http.http_utils import HttpUtils
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.user.user_interface import UserInterface

pytestmark = pytest.mark.anyio

#: A password a test user carries; a fixture, not a secret.
_HASHED = "hashed"


@final
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
        return ResponseFactory().create_response(403)


def _authenticator(
    *,
    success: _Success | None = None,
    failure: _Failure | None = None,
    options: dict[str, object] | None = None,
) -> JsonLoginAuthenticator:
    return JsonLoginAuthenticator(
        HttpUtils(ResponseFactory()),
        _Provider(),
        ResponseFactory(),
        success,
        failure,
        options,
    )


def _json_request(
    *,
    path: str = "/login",
    content_type: str = "application/json",
    parsed_body: object | None = None,
) -> ServerRequestInterface:
    return make_message(
        method="POST",
        path=path,
        headers={"Content-Type": content_type},
        parsed_body=parsed_body,
    )


def test_a_json_request_is_supported() -> None:
    assert _authenticator().supports(_json_request(parsed_body={"username": "alice"})) is True


def test_a_request_with_no_json_content_type_is_refused() -> None:
    reasons = UnsupportedReasons()
    message = _json_request(content_type="text/plain")
    asked = message.with_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS, reasons)

    assert _authenticator().supports(asked) is False
    assert reasons.all() == ('the "Content-Type" header "text/plain" is not a JSON one',)


def test_a_request_off_the_check_path_is_refused() -> None:
    reasons = UnsupportedReasons()
    message = _json_request(path="/elsewhere", parsed_body={})
    asked = message.with_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS, reasons)

    assert _authenticator(options={"check_path": "/login"}).supports(asked) is False


async def test_the_document_reads_into_a_passport() -> None:
    passport = await _authenticator().authenticate(
        _json_request(parsed_body={"username": "alice", "password": "secret"}),
    )

    assert await passport.get_user_badge().get_user() is not None


async def test_a_nested_path_walks_the_document() -> None:
    passport = await _authenticator(
        options={"username_path": "user.name", "password_path": "user.pass"},
    ).authenticate(
        _json_request(parsed_body={"user": {"name": "alice", "pass": "secret"}}),
    )

    assert (await passport.get_user_badge().get_user()).get_user_identifier() == "alice"


async def test_a_missing_field_fails_the_login() -> None:
    with pytest.raises(BadCredentialsError):
        _ = await _authenticator().authenticate(_json_request(parsed_body={"username": "alice"}))


async def test_an_empty_field_fails_the_login() -> None:
    with pytest.raises(BadCredentialsError):
        _ = await _authenticator().authenticate(
            _json_request(parsed_body={"username": "alice", "password": ""}),
        )


async def test_a_body_that_is_no_object_fails_the_login() -> None:
    with pytest.raises(BadCredentialsError):
        _ = await _authenticator().authenticate(_json_request(parsed_body=["alice"]))


async def test_the_password_is_erased_from_the_remember_me_parameters() -> None:
    passport = await _authenticator().authenticate(
        _json_request(parsed_body={"username": "alice", "password": "secret", "keep": "yes"}),
    )

    badge = passport.get_badge(RememberMeBadge)
    assert badge is not None
    assert badge.get_parameters() == {"username": "alice", "password": None, "keep": "yes"}


async def test_the_token_is_a_username_password_one() -> None:
    authenticator = _authenticator()
    passport = await authenticator.authenticate(
        _json_request(parsed_body={"username": "alice", "password": "secret"}),
    )

    token = await authenticator.create_token(passport, "main")

    assert isinstance(token, UsernamePasswordToken)
    assert token.get_user_identifier() == "alice"
    assert token.get_firewall_name() == "main"


async def test_a_success_delegates_to_the_handler() -> None:
    success = _Success()
    token = NullToken()

    response = await _authenticator(success=success).on_authentication_success(
        _json_request(),
        token,
        "main",
    )

    assert response is not None
    assert response.get_status_code() == 200
    assert success.tokens == [token]


async def test_a_success_without_a_handler_lets_the_request_go_on() -> None:
    response = await _authenticator().on_authentication_success(
        _json_request(), NullToken(), "main"
    )

    assert response is None


async def test_a_failure_without_a_handler_answers_a_401_with_the_errors_message() -> None:
    error = BadCredentialsError("The password is invalid.")

    response = await _authenticator().on_authentication_failure(_json_request(), error)

    assert response is not None
    assert response.get_status_code() == 401
    assert response.get_header_line("Content-Type") == "application/json"


async def test_a_failure_delegates_to_the_handler() -> None:
    failure = _Failure()
    error = BadCredentialsError("failed")

    response = await _authenticator(failure=failure).on_authentication_failure(
        _json_request(), error
    )

    assert response is not None
    assert response.get_status_code() == 403
    assert failure.errors == [error]


def test_the_login_is_the_users_own_act() -> None:
    assert _authenticator().is_interactive() is True


def test_it_satisfies_the_interactive_interface() -> None:

    assert isinstance(_authenticator(), InteractiveAuthenticatorInterface)
