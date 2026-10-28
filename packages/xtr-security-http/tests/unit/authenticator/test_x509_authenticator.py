"""The X.509 authenticator: the user their certificate identifies."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_security_core.authentication.token.pre_authenticated_token import PreAuthenticatedToken
from xtr_security_core.exception import BadCredentialsError
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_core.user.in_memory_user_provider import InMemoryUserProvider

from tests.support.messages import make_message
from xtr_security_http.authenticator.debug.unsupported_reasons import UnsupportedReasons
from xtr_security_http.authenticator.passport.badge.pre_authenticated_user_badge import (
    PreAuthenticatedUserBadge,
)
from xtr_security_http.authenticator.x509_authenticator import X509Authenticator
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.authentication.token.storage.token_storage_interface import (
        TokenStorageInterface,
    )

pytestmark = pytest.mark.anyio


@final
class _NoTokenStorage:
    """A token storage that holds nothing, for the extraction tests."""

    __slots__ = ()

    def get_token(self) -> None:
        """Answer no token: nothing was settled before the request."""

    def set_token(self, token: object) -> None:
        """Refuse: no test of the extraction reaches a write."""
        del token
        raise AssertionError("no test of the extraction reaches a write")


def _authenticator(
    storage: TokenStorageInterface,
    *,
    credential_user_identifier: str = "emailAddress",
    identifier: str = "ada",
) -> X509Authenticator:
    """Build the authenticator over the provider holding the named user."""
    return X509Authenticator(
        InMemoryUserProvider({identifier: InMemoryUser(identifier, roles=("ROLE_USER",))}),
        storage,
        "main",
        credential_user_identifier=credential_user_identifier,
    )


def _request(
    server_params: Mapping[str, object] | None = None,
    reasons: UnsupportedReasons | None = None,
) -> ServerRequestInterface:
    """Build a request carrying the environment asked for."""
    message = make_message(server_params=server_params)
    if reasons is not None:
        message = message.with_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS, reasons)
    return message


def test_supports_answers_true_when_the_certificate_names_an_email() -> None:
    authenticator = _authenticator(_NoTokenStorage())

    assert authenticator.supports(_request({"SSL_CLIENT_S_DN_Email": "ada@example.com"})) is True


def test_the_email_is_read_from_the_distinguished_name_when_the_key_is_absent() -> None:
    authenticator = _authenticator(_NoTokenStorage())
    request = _request({"SSL_CLIENT_S_DN": "CN=Ada, emailAddress=ada@example.com, O=The Firm"})

    assert authenticator.extract_username(request) == "ada@example.com"


def test_the_dotted_oid_spelling_of_email_address_matches_too() -> None:
    authenticator = _authenticator(_NoTokenStorage())
    request = _request({"SSL_CLIENT_S_DN": "1.2.840.113549.1.9.1=ada@example.com"})

    assert authenticator.extract_username(request) == "ada@example.com"


def test_a_value_read_from_the_distinguished_name_is_trimmed() -> None:
    authenticator = _authenticator(_NoTokenStorage())
    request = _request({"SSL_CLIENT_S_DN": "emailAddress=  ada@example.com "})

    assert authenticator.extract_username(request) == "ada@example.com"


def test_a_custom_credential_user_identifier_is_read_from_the_name() -> None:
    authenticator = _authenticator(
        _NoTokenStorage(),
        credential_user_identifier="CN",
    )
    request = _request({"SSL_CLIENT_S_DN": "emailAddress=none@example.com, CN=Ada Lovelace"})

    assert authenticator.extract_username(request) == "Ada Lovelace"


def test_missing_credentials_are_refused() -> None:
    reasons = UnsupportedReasons()
    authenticator = _authenticator(_NoTokenStorage())

    supported = authenticator.supports(_request({}, reasons))

    assert supported is False
    assert reasons.all() == (
        'SSL credentials not found: "SSL_CLIENT_S_DN_Email", "SSL_CLIENT_S_DN".',
    )


def test_a_name_without_the_identifier_is_refused() -> None:
    authenticator = _authenticator(_NoTokenStorage())
    request = _request({"SSL_CLIENT_S_DN": "CN=Ada, O=The Firm"})

    with pytest.raises(BadCredentialsError) as raised:
        _ = authenticator.extract_username(request)

    assert str(raised.value) == (
        'SSL credentials not found: "SSL_CLIENT_S_DN_Email", "SSL_CLIENT_S_DN".'
    )


def test_an_email_identifier_requires_an_email_shaped_value() -> None:
    authenticator = _authenticator(_NoTokenStorage())
    request = _request({"SSL_CLIENT_S_DN": "emailAddress=not-an-email"})

    with pytest.raises(BadCredentialsError):
        _ = authenticator.extract_username(request)


async def test_authenticates_the_user_the_certificate_names() -> None:
    user = InMemoryUser("ada@example.com", roles=("ROLE_USER",))
    authenticator = _authenticator(_NoTokenStorage(), identifier="ada@example.com")

    passport = await authenticator.authenticate(
        _request({"SSL_CLIENT_S_DN_Email": "ada@example.com"}),
    )

    assert passport.has_badge(PreAuthenticatedUserBadge)
    assert await passport.get_user() == user

    token = await authenticator.create_token(passport, "main")

    assert isinstance(token, PreAuthenticatedToken)
    assert token.get_user_identifier() == "ada@example.com"
    assert token.get_firewall_name() == "main"
