"""The signer is one immutable value, and its reading names no key."""

from __future__ import annotations

from tests.support.signing import ISSUER, KEY_ID, make_signer


def test_it_carries_the_audience_it_was_given() -> None:
    assert make_signer("https://api.example.com").audience == "https://api.example.com"


def test_it_carries_no_audience_by_default() -> None:
    assert make_signer().audience is None


def test_its_reading_names_the_issuer_the_audience_and_the_key_id() -> None:
    reading = repr(make_signer("https://api.example.com"))

    assert ISSUER in reading
    assert "https://api.example.com" in reading
    assert KEY_ID in reading


def test_its_reading_names_the_provider_by_type_alone() -> None:
    reading = repr(make_signer())

    assert "JoserfcJwsProvider" in reading
    assert "object at 0x" not in reading
