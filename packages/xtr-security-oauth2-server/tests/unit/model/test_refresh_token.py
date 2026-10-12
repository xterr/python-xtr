"""A stored refresh token names the access token it was issued beside."""

from __future__ import annotations

from datetime import UTC, datetime

from xtr_security_oauth2_server.model.access_token import AccessToken
from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.model.refresh_token import RefreshToken
from xtr_security_oauth2_server.model.refresh_token_interface import RefreshTokenInterface

_EXPIRY = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)


def _access_token() -> AccessToken:
    return AccessToken("at-1", _EXPIRY, Client("C", "client-1", None), "user-1", ())


def _refresh_token(access_token: AccessToken | None = None) -> RefreshToken:
    return RefreshToken("rt-identifier-1", _EXPIRY, access_token)


def test_it_declares_the_refresh_token_contract() -> None:
    assert RefreshTokenInterface in RefreshToken.__mro__


def test_it_reads_as_its_identifier() -> None:
    assert str(_refresh_token()) == "rt-identifier-1"


def test_it_reports_the_identifier_it_was_stored_under() -> None:
    assert _refresh_token().get_identifier() == "rt-identifier-1"


def test_it_reports_when_it_stops_being_accepted() -> None:
    assert _refresh_token().get_expiry() == _EXPIRY


def test_it_reports_the_access_token_it_came_with() -> None:
    access_token = _access_token()

    assert _refresh_token(access_token).get_access_token() is access_token


def test_it_names_no_access_token_when_none_was_stored() -> None:
    assert _refresh_token().get_access_token() is None


def test_it_is_not_revoked_when_stored() -> None:
    assert _refresh_token().is_revoked() is False


def test_it_is_revoked_once_revoked() -> None:
    token = _refresh_token()

    _ = token.revoke()

    assert token.is_revoked() is True


def test_revoking_answers_the_token_so_a_caller_can_chain() -> None:
    token = _refresh_token()

    assert token.revoke() is token


def test_its_reading_cuts_its_identifier_short() -> None:
    assert repr(_refresh_token()) == "RefreshToken(identifier='rt-ident...')"
