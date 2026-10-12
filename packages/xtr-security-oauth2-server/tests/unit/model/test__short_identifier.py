"""How much of an identifier a reading of a stored model may show."""

from __future__ import annotations

from xtr_security_oauth2_server.model._short_identifier import short_identifier

__all__ = []


def test_it_returns_the_identifier_when_it_fits_in_the_shown_length() -> None:
    """Given: an identifier shorter than or equal to 8 characters.

    When: short_identifier is called.

    Then: the full identifier is returned.
    """
    assert short_identifier("abc") == "abc"
    assert short_identifier("12345678") == "12345678"


def test_it_truncates_and_marks_when_identifier_exceeds_shown_length() -> None:
    """Given: an identifier longer than 8 characters.

    When: short_identifier is called.

    Then: the first 8 characters are returned with an ellipsis appended.
    """
    assert short_identifier("123456789") == "12345678..."
    assert short_identifier("abcdefghijklmnop") == "abcdefgh..."
