"""The token-state trait holds the client, the window and the scopes."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.support.entities import AccessToken, make_client, make_scope

_EXPIRES_AT = datetime(2026, 3, 4, 6, 6, 7, tzinfo=UTC)


def test_it_names_no_user_until_one_is_set() -> None:
    assert AccessToken().get_user_identifier() is None


def test_it_hands_back_the_user_it_was_given() -> None:
    token = AccessToken()
    token.set_user_identifier("user-1")

    assert token.get_user_identifier() == "user-1"


def test_it_hands_back_the_client_it_was_given() -> None:
    client = make_client()
    token = AccessToken()
    token.set_client(client)

    assert token.get_client() is client


def test_it_hands_back_the_expiry_it_was_given() -> None:
    token = AccessToken()
    token.set_expiry_date_time(_EXPIRES_AT)

    assert token.get_expiry_date_time() == _EXPIRES_AT


def test_reading_an_expiry_nobody_set_refuses() -> None:
    with pytest.raises(AttributeError):
        _ = AccessToken().get_expiry_date_time()


def test_it_carries_no_scopes_until_one_is_added() -> None:
    assert AccessToken().get_scopes() == ()


def test_it_keeps_the_scopes_in_the_order_they_were_added() -> None:
    token = AccessToken()
    for identifier in ("write", "read", "admin"):
        token.add_scope(make_scope(identifier))

    assert [scope.get_identifier() for scope in token.get_scopes()] == ["write", "read", "admin"]


def test_a_scope_added_twice_is_carried_once() -> None:
    token = AccessToken()
    token.add_scope(make_scope("read"))
    token.add_scope(make_scope("read"))

    assert [scope.get_identifier() for scope in token.get_scopes()] == ["read"]


def test_a_scope_added_again_keeps_the_place_it_first_took() -> None:
    token = AccessToken()
    token.add_scope(make_scope("read"))
    token.add_scope(make_scope("write"))
    last = make_scope("read")
    token.add_scope(last)

    assert [scope.get_identifier() for scope in token.get_scopes()] == ["read", "write"]
    assert token.get_scopes()[0] is last
