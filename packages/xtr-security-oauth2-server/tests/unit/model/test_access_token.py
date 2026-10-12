"""A stored access token: what it was issued for, and whether it still counts."""

from __future__ import annotations

from datetime import UTC, datetime

from xtr_security_oauth2_server.model.access_token import AccessToken
from xtr_security_oauth2_server.model.access_token_interface import AccessTokenInterface
from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.value_object.scope import Scope

_EXPIRY = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)


def _access_token(identifier: str = "at-identifier-1") -> AccessToken:
    return AccessToken(
        identifier,
        _EXPIRY,
        Client("Test client", "client-1", "hashed"),
        "user-1",
        (Scope("read"),),
    )


def test_it_declares_the_access_token_contract() -> None:
    assert AccessTokenInterface in AccessToken.__mro__


def test_it_reads_as_its_identifier() -> None:
    assert str(_access_token()) == "at-identifier-1"


def test_it_reports_the_identifier_it_was_stored_under() -> None:
    assert _access_token().get_identifier() == "at-identifier-1"


def test_it_reports_when_it_stops_being_accepted() -> None:
    assert _access_token().get_expiry() == _EXPIRY


def test_it_reports_the_resource_owner_it_acts_for() -> None:
    assert _access_token().get_user_identifier() == "user-1"


def test_it_names_no_resource_owner_when_the_client_acts_for_itself() -> None:
    token = AccessToken("at-1", _EXPIRY, Client("C", "client-1", None), None, ())

    assert token.get_user_identifier() is None


def test_it_reports_the_client_it_was_issued_to() -> None:
    assert _access_token().get_client().get_identifier() == "client-1"


def test_it_reports_the_scopes_it_carries() -> None:
    assert _access_token().get_scopes() == (Scope("read"),)


def test_it_is_not_revoked_when_stored() -> None:
    assert _access_token().is_revoked() is False


def test_it_is_revoked_once_revoked() -> None:
    token = _access_token()

    _ = token.revoke()

    assert token.is_revoked() is True


def test_revoking_answers_the_token_so_a_caller_can_chain() -> None:
    token = _access_token()

    assert token.revoke() is token


def test_its_reading_cuts_its_identifier_short() -> None:
    reading = repr(_access_token())

    assert reading == "AccessToken(identifier='at-ident...')"
