"""The client a grant reads while it handles one request."""

from __future__ import annotations

from xtr_security_oauth2_server.entities.client_entity_interface import ClientEntityInterface
from xtr_security_oauth2_server.entity.client import Client


def _client() -> Client:
    client = Client()
    client.set_identifier("client-1")
    client.set_name("Test client")
    client.set_redirect_uri(["https://client.example.com/callback"])
    client.set_confidential(True)

    return client


def test_it_satisfies_the_client_contract() -> None:
    assert ClientEntityInterface in Client.__mro__
    assert isinstance(_client(), ClientEntityInterface)


def test_it_reports_the_name_it_was_given() -> None:
    assert _client().get_name() == "Test client"


def test_it_reports_the_redirect_uris_it_was_given() -> None:
    assert _client().get_redirect_uri() == ["https://client.example.com/callback"]


def test_it_reports_whether_it_can_keep_a_secret() -> None:
    assert _client().is_confidential() is True


def test_it_is_public_until_it_is_told_otherwise() -> None:
    assert Client().is_confidential() is False


def test_it_refuses_an_unhashed_code_challenge_until_allowed_one() -> None:
    assert _client().is_plain_text_pkce_allowed() is False


def test_it_allows_an_unhashed_code_challenge_once_told_to() -> None:
    client = _client()

    client.set_allow_plain_text_pkce(True)

    assert client.is_plain_text_pkce_allowed() is True


def test_it_allows_every_grant_when_none_was_named() -> None:
    assert _client().supports_grant_type("authorization_code") is True


def test_it_allows_a_grant_it_was_registered_for() -> None:
    client = _client()

    client.set_allowed_grant_types(["authorization_code", "refresh_token"])

    assert client.supports_grant_type("refresh_token") is True


def test_it_refuses_a_grant_it_was_not_registered_for() -> None:
    client = _client()

    client.set_allowed_grant_types(["authorization_code"])

    assert client.supports_grant_type("password") is False


def test_its_reading_names_only_the_identifier() -> None:
    assert repr(_client()) == "Client(identifier='client-1')"
