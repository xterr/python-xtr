"""The remote-user authenticator: the account the server in front vouched for."""

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
from xtr_security_http.authenticator.remote_user_authenticator import RemoteUserAuthenticator
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
    user_key: str = "REMOTE_USER",
) -> RemoteUserAuthenticator:
    """Build the authenticator over the provider holding ada."""
    return RemoteUserAuthenticator(
        InMemoryUserProvider({"ada": InMemoryUser("ada", roles=("ROLE_USER",))}),
        storage,
        "main",
        user_key,
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


def test_supports_answers_true_for_a_request_the_server_identifies() -> None:
    authenticator = _authenticator(_NoTokenStorage())

    assert authenticator.supports(_request({"REMOTE_USER": "ada"})) is True


def test_a_missing_user_key_is_refused() -> None:
    reasons = UnsupportedReasons()
    authenticator = _authenticator(_NoTokenStorage())

    supported = authenticator.supports(_request({}, reasons))

    assert supported is False
    assert reasons.all() == ('User key was not found: "REMOTE_USER".',)


def test_an_empty_user_value_reads_as_no_user() -> None:
    reasons = UnsupportedReasons()
    authenticator = _authenticator(_NoTokenStorage())

    supported = authenticator.supports(_request({"REMOTE_USER": ""}, reasons))

    assert supported is False
    assert reasons.all() == ("no user identifier was found in the request",)


def test_a_value_that_is_not_text_reads_as_no_user() -> None:
    authenticator = _authenticator(_NoTokenStorage())

    assert authenticator.supports(_request({"REMOTE_USER": 123})) is False


def test_a_custom_user_key_is_read() -> None:
    authenticator = _authenticator(_NoTokenStorage(), user_key="AUTH_USER")

    assert authenticator.supports(_request({"AUTH_USER": "ada"})) is True
    assert authenticator.supports(_request({"REMOTE_USER": "ada"})) is False


async def test_authenticates_the_user_the_server_named() -> None:
    user = InMemoryUser("ada", roles=("ROLE_USER",))
    authenticator = _authenticator(_NoTokenStorage())

    passport = await authenticator.authenticate(_request({"REMOTE_USER": "ada"}))

    assert passport.has_badge(PreAuthenticatedUserBadge)
    assert await passport.get_user() == user

    token = await authenticator.create_token(passport, "main")

    assert isinstance(token, PreAuthenticatedToken)
    assert token.get_user_identifier() == "ada"
    assert token.get_firewall_name() == "main"


async def test_authenticate_refuses_a_request_the_server_did_not_identify() -> None:
    authenticator = _authenticator(_NoTokenStorage())

    with pytest.raises(BadCredentialsError) as raised:
        _ = await authenticator.authenticate(_request({}))

    assert str(raised.value) == 'User key was not found: "REMOTE_USER".'
