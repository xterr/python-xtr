"""A client's registration: what it is called, what it may do, and its secret."""

from __future__ import annotations

from typing import Final

from xtr_security_oauth2_server.model.client import Client
from xtr_security_oauth2_server.value_object.grant import Grant
from xtr_security_oauth2_server.value_object.redirect_uri import RedirectUri
from xtr_security_oauth2_server.value_object.scope import Scope

#: The stored hash a client holds here. Not a password: a client's secret is
#: kept as a hash, and nothing in these tests compares it.
_HASH: Final[str] = "hashed-secret"


def _client(secret: str | None = _HASH) -> Client:
    return Client("Test client", "client-1", secret)


def test_it_reports_the_name_it_was_registered_with() -> None:
    assert _client().get_name() == "Test client"


def test_it_can_be_renamed() -> None:
    client = _client()

    _ = client.set_name("Another name")

    assert client.get_name() == "Another name"


def test_it_reports_the_identifier_it_was_registered_under() -> None:
    assert _client().get_identifier() == "client-1"


def test_it_reports_the_secret_it_holds() -> None:
    assert _client().get_secret() == "hashed-secret"


def test_its_secret_can_be_replaced() -> None:
    client = _client()

    client.set_secret("rehashed-secret")

    assert client.get_secret() == "rehashed-secret"


def test_it_is_registered_with_no_redirect_uri() -> None:
    assert _client().get_redirect_uris() == ()


def test_it_keeps_the_redirect_uris_it_is_given() -> None:
    client = _client()
    first = RedirectUri("https://a.example.com/cb")
    second = RedirectUri("https://b.example.com/cb")

    _ = client.set_redirect_uris(first, second)

    assert client.get_redirect_uris() == (first, second)


def test_it_is_registered_with_no_grant() -> None:
    assert _client().get_grants() == ()


def test_it_keeps_the_grants_it_is_given() -> None:
    client = _client()

    _ = client.set_grants(Grant("authorization_code"), Grant("refresh_token"))

    assert client.get_grants() == (Grant("authorization_code"), Grant("refresh_token"))


def test_it_is_registered_with_no_scope() -> None:
    assert _client().get_scopes() == ()


def test_it_keeps_the_scopes_it_is_given() -> None:
    client = _client()

    _ = client.set_scopes(Scope("read"))

    assert client.get_scopes() == (Scope("read"),)


def test_it_is_active_when_registered() -> None:
    assert _client().is_active() is True


def test_it_can_be_deactivated() -> None:
    client = _client()

    _ = client.set_active(False)

    assert client.is_active() is False


def test_it_is_confidential_when_it_holds_a_secret() -> None:
    assert _client().is_confidential() is True


def test_it_is_public_when_it_holds_no_secret() -> None:
    assert _client(None).is_confidential() is False


def test_it_is_public_when_its_secret_is_empty() -> None:
    assert _client("").is_confidential() is False


def test_it_refuses_the_plain_code_challenge_method_when_registered() -> None:
    assert _client().is_plain_text_pkce_allowed() is False


def test_it_can_be_allowed_the_plain_code_challenge_method() -> None:
    client = _client()

    _ = client.set_allow_plain_text_pkce(True)

    assert client.is_plain_text_pkce_allowed() is True


def test_its_setters_answer_the_client_so_a_caller_can_chain_them() -> None:
    client = _client()

    chained = client.set_active(True).set_allow_plain_text_pkce(True).set_scopes(Scope("read"))

    assert chained is client


def test_its_reading_holds_neither_the_secret_nor_the_scopes() -> None:
    client = _client()
    _ = client.set_scopes(Scope("read"))

    reading = repr(client)

    assert "hashed-secret" not in reading
    assert "read" not in reading
    assert reading == "Client(identifier='client-1')"
