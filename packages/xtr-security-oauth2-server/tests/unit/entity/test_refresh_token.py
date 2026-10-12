"""The refresh-token entity, tied to the access token it was issued beside."""

from __future__ import annotations

from datetime import UTC, datetime

from xtr_security_oauth2_server_core.entities.refresh_token_entity_interface import (
    RefreshTokenEntityInterface,
)

from xtr_security_oauth2_server.entity.access_token import AccessToken
from xtr_security_oauth2_server.entity.refresh_token import RefreshToken


def _refresh_token() -> RefreshToken:
    token = RefreshToken()
    token.set_identifier("rt-identifier-1")
    token.set_expiry_date_time(datetime(2026, 4, 3, 5, 6, 7, tzinfo=UTC))

    return token


def test_it_satisfies_the_refresh_token_contract() -> None:
    assert RefreshTokenEntityInterface in RefreshToken.__mro__
    assert isinstance(_refresh_token(), RefreshTokenEntityInterface)


def test_it_is_built_with_no_arguments_so_a_repository_can_mint_one() -> None:
    assert repr(RefreshToken()) == "RefreshToken(identifier=unset)"


def test_it_names_the_access_token_it_was_tied_to() -> None:
    token = _refresh_token()
    access_token = AccessToken()
    access_token.set_identifier("at-1")

    token.set_access_token(access_token)

    assert token.get_access_token() is access_token


def test_its_reading_cuts_its_identifier_short() -> None:
    assert repr(_refresh_token()) == "RefreshToken(identifier='rt-ident...')"
