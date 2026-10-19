"""The HTTP basic authenticator: a challenge answered by the same challenge."""

from __future__ import annotations

from base64 import b64encode
from typing import TYPE_CHECKING, final

import pytest
from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core.authentication.token.username_password_token import UsernamePasswordToken
from xtr_security_core.exception import BadCredentialsError
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.messages import make_message
from tests.support.recording_logger import RecordingLogger
from xtr_security_http.authenticator.debug.unsupported_reasons import UnsupportedReasons
from xtr_security_http.authenticator.http_basic_authenticator import HttpBasicAuthenticator
from xtr_security_http.authenticator.passport.credentials.password_credentials import (
    PasswordCredentials,
)
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface
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


def _authenticator(
    *,
    realm: str = "Secure Area",
    logger: RecordingLogger | None = None,
) -> HttpBasicAuthenticator:
    return HttpBasicAuthenticator(realm, _Provider(), ResponseFactory(), logger)


def _basic_request(credentials: str) -> ServerRequestInterface:
    encoded = b64encode(credentials.encode()).decode()
    return make_message(headers={"Authorization": f"Basic {encoded}"})


def test_a_request_with_basic_credentials_is_supported() -> None:
    assert _authenticator().supports(_basic_request("alice:secret")) is True


def test_a_request_without_credentials_is_refused_with_a_reason() -> None:
    reasons = UnsupportedReasons()
    message = make_message()
    asked = message.with_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS, reasons)

    assert _authenticator().supports(asked) is False
    assert reasons.all() == (
        'the request carries no HTTP basic credentials, as no "Authorization: Basic" header is set',
    )


def test_a_request_with_another_scheme_is_refused() -> None:
    assert (
        _authenticator().supports(make_message(headers={"Authorization": "Bearer token"})) is False
    )


async def test_the_credentials_read_into_a_passport() -> None:
    passport = await _authenticator().authenticate(_basic_request("alice:secret"))

    assert (await passport.get_user_badge().get_user()).get_user_identifier() == "alice"


async def test_a_password_may_carry_colons() -> None:
    passport = await _authenticator().authenticate(_basic_request("alice:pass:word"))

    credentials = passport.get_badge(PasswordCredentials)
    assert credentials is not None
    assert credentials.get_password() == "pass:word"


async def test_credentials_that_do_not_decode_fail_the_login() -> None:
    message = make_message(headers={"Authorization": "Basic !!!not-base64!!!"})

    with pytest.raises(BadCredentialsError):
        _ = await _authenticator().authenticate(message)


async def test_credentials_that_name_no_username_fail_the_login() -> None:
    message = make_message(headers={"Authorization": "Basic OnNlY3JldA=="})

    with pytest.raises(BadCredentialsError):
        _ = await _authenticator().authenticate(message)


async def test_the_token_is_a_username_password_one() -> None:
    authenticator = _authenticator()
    passport = await authenticator.authenticate(_basic_request("alice:secret"))

    token = await authenticator.create_token(passport, "main")

    assert isinstance(token, UsernamePasswordToken)
    assert token.get_user_identifier() == "alice"
    assert token.get_firewall_name() == "main"


async def test_the_entry_point_answers_a_401_naming_the_realm() -> None:
    response = await _authenticator(realm="Secure Area").start(make_message())

    assert response is not None
    assert response.get_status_code() == 401
    assert response.get_header_line("WWW-Authenticate") == 'Basic realm="Secure Area"'
    assert response.get_header_line("Cache-Control") == "no-store"


async def test_a_failed_attempt_is_logged_and_answered_with_the_challenge_again() -> None:
    logger = RecordingLogger()
    error = BadCredentialsError("failed")

    response = await _authenticator(logger=logger).on_authentication_failure(
        _basic_request("alice:wrong"),
        error,
    )

    assert logger.messages("info") == ["Basic authentication failed for user."]
    assert response is not None
    assert response.get_status_code() == 401
    assert response.get_header_line("WWW-Authenticate") == 'Basic realm="Secure Area"'
