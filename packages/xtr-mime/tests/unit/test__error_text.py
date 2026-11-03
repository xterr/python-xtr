"""What an error repeats of a value it was given: escaped, and never more than 64 characters."""

from __future__ import annotations

from xtr_mime._error_text import capped, escaped


def test_a_value_is_escaped_as_repr_shows_it() -> None:
    assert escaped("a\r\nb\x00\udc80") == "a\\r\\nb\\x00\\udc80"


def test_a_short_value_is_shown_whole() -> None:
    assert capped("a\r\nb") == "a\\r\\nb"


def test_a_value_of_64_characters_is_shown_whole() -> None:
    assert capped("a" * 64) == "a" * 64


def test_a_longer_value_is_cut_to_its_first_64_characters() -> None:
    assert capped("a" * 64 + "\r\nBcc: victim@example.com") == "a" * 64 + "…"
