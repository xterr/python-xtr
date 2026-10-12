"""The access-token entity: the traits composed into something a grant can issue."""

from __future__ import annotations

from datetime import UTC, datetime

from tests.support.signing import make_signer
from xtr_security_oauth2_server.entities.access_token_entity_interface import (
    AccessTokenEntityInterface,
)
from xtr_security_oauth2_server.entity.access_token import AccessToken
from xtr_security_oauth2_server.entity.client import Client
from xtr_security_oauth2_server.entity.scope import Scope


def _client() -> Client:
    client = Client()
    client.set_identifier("client-1")
    client.set_name("Test client")
    client.set_redirect_uri([])
    client.set_confidential(True)

    return client


def _access_token() -> AccessToken:
    token = AccessToken()
    token.set_identifier("at-identifier-1")
    token.set_client(_client())
    token.set_expiry_date_time(datetime(2026, 3, 4, 6, 6, 7, tzinfo=UTC))

    return token


def test_it_satisfies_the_access_token_contract() -> None:
    assert AccessTokenEntityInterface in AccessToken.__mro__
    assert isinstance(_access_token(), AccessTokenEntityInterface)


def test_it_is_built_with_no_arguments_so_a_repository_can_mint_one() -> None:
    assert AccessToken().get_scopes() == ()


def test_it_carries_the_scopes_it_is_given() -> None:
    token = _access_token()
    scope = Scope()
    scope.set_identifier("read")

    token.add_scope(scope)

    assert [str(carried) for carried in token.get_scopes()] == ["read"]


def test_it_signs_itself_once_handed_a_signer() -> None:
    token = _access_token()
    token.set_private_key(make_signer())

    assert token.to_string().count(".") == 2


def test_its_reading_cuts_its_identifier_short() -> None:
    assert repr(_access_token()) == "AccessToken(identifier='at-ident...')"
