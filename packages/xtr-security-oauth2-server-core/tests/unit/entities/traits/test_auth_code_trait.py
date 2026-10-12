"""An authorization code remembers the redirect URI it was asked for."""

from __future__ import annotations

from tests.support.entities import AuthCode


def test_it_names_no_redirect_uri_until_one_is_set() -> None:
    assert AuthCode().get_redirect_uri() is None


def test_it_hands_back_the_redirect_uri_it_was_given() -> None:
    code = AuthCode()
    code.set_redirect_uri("https://client.example.com/callback")

    assert code.get_redirect_uri() == "https://client.example.com/callback"
