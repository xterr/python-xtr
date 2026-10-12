"""The authorization-code entity, carrying the redirect URI it was asked for."""

from __future__ import annotations

from datetime import UTC, datetime

from xtr_security_oauth2_server_core.entities import AuthCodeEntityInterface

from xtr_security_oauth2_server.entity.auth_code import AuthCode
from xtr_security_oauth2_server.entity.client import Client


def _auth_code() -> AuthCode:
    client = Client()
    client.set_identifier("client-1")
    client.set_name("Test client")
    client.set_redirect_uri([])
    client.set_confidential(True)

    code = AuthCode()
    code.set_identifier("ac-identifier-1")
    code.set_client(client)
    code.set_expiry_date_time(datetime(2026, 3, 4, 5, 16, 7, tzinfo=UTC))

    return code


def test_it_satisfies_the_auth_code_contract() -> None:
    assert AuthCodeEntityInterface in AuthCode.__mro__
    assert isinstance(_auth_code(), AuthCodeEntityInterface)


def test_it_is_built_with_no_arguments_so_a_repository_can_mint_one() -> None:
    assert AuthCode().get_redirect_uri() is None


def test_it_remembers_the_redirect_uri_it_was_issued_for() -> None:
    code = _auth_code()

    code.set_redirect_uri("https://client.example.com/callback")

    assert code.get_redirect_uri() == "https://client.example.com/callback"


def test_its_reading_cuts_its_identifier_short() -> None:
    assert repr(_auth_code()) == "AuthCode(identifier='ac-ident...')"
