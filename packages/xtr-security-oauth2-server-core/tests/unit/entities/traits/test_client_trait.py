"""A client reports its registration, and accepts every grant unless told otherwise."""

from __future__ import annotations

from tests.support.entities import Client, make_client


def test_it_hands_back_the_name_it_was_given() -> None:
    assert make_client(name="Device app").get_name() == "Device app"


def test_it_hands_back_a_single_redirect_uri_as_it_was_given() -> None:
    client = make_client(redirect_uri="https://client.example.com/callback")

    assert client.get_redirect_uri() == "https://client.example.com/callback"


def test_it_hands_back_several_redirect_uris_as_they_were_given() -> None:
    uris = ("https://client.example.com/callback", "https://client.example.com/other")

    assert make_client(redirect_uri=uris).get_redirect_uri() == uris


def test_it_is_public_until_it_is_told_it_is_confidential() -> None:
    assert Client().is_confidential() is False


def test_it_hands_back_the_confidentiality_it_was_given() -> None:
    assert make_client(confidential=True).is_confidential() is True


def test_it_supports_every_grant_type_by_default() -> None:
    client = make_client()

    assert client.supports_grant_type("authorization_code") is True
    assert client.supports_grant_type("urn:ietf:params:oauth:grant-type:device_code") is True
    assert client.supports_grant_type("anything-at-all") is True
