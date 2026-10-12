"""A stored authorization code: what it was issued for, and whether it was redeemed."""

from __future__ import annotations

from datetime import UTC, datetime

from xtr_security_oauth2_server.model.authorization_code import AuthorizationCode
from xtr_security_oauth2_server.model.authorization_code_interface import (
    AuthorizationCodeInterface,
)
from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.value_object.scope import Scope

_EXPIRY = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)


def _authorization_code(identifier: str = "ac-identifier-1") -> AuthorizationCode:
    return AuthorizationCode(
        identifier,
        _EXPIRY,
        Client("Test client", "client-1", "hashed"),
        "user-1",
        (Scope("read"),),
    )


def test_it_declares_the_authorization_code_contract() -> None:
    assert AuthorizationCodeInterface in AuthorizationCode.__mro__


def test_it_reads_as_its_identifier() -> None:
    assert str(_authorization_code()) == "ac-identifier-1"


def test_it_reports_the_identifier_it_was_stored_under() -> None:
    assert _authorization_code().get_identifier() == "ac-identifier-1"


def test_it_reports_when_it_stops_being_accepted() -> None:
    assert _authorization_code().get_expiry() == _EXPIRY


def test_it_reports_the_resource_owner_it_was_issued_for() -> None:
    assert _authorization_code().get_user_identifier() == "user-1"


def test_it_reports_the_client_it_was_issued_to() -> None:
    assert _authorization_code().get_client().get_identifier() == "client-1"


def test_it_reports_the_scopes_consented_to() -> None:
    assert _authorization_code().get_scopes() == (Scope("read"),)


def test_it_is_not_revoked_when_stored() -> None:
    assert _authorization_code().is_revoked() is False


def test_it_is_revoked_once_redeemed() -> None:
    code = _authorization_code()

    _ = code.revoke()

    assert code.is_revoked() is True


def test_revoking_answers_the_code_so_a_caller_can_chain() -> None:
    code = _authorization_code()

    assert code.revoke() is code


def test_its_reading_cuts_its_identifier_short() -> None:
    assert repr(_authorization_code()) == "AuthorizationCode(identifier='ac-ident...')"
