"""What an error repeats of a value it was given: escaped, and never more than 64 characters."""

from __future__ import annotations

import codecs

import pytest

from xtr_mime import TextPart
from xtr_mime._error_text import body_charset_error, capped, check_charset, escaped
from xtr_mime.exception import InvalidArgumentError


def test_a_value_is_escaped_as_repr_shows_it() -> None:
    assert escaped("a\r\nb\x00\udc80") == "a\\r\\nb\\x00\\udc80"


def test_a_short_value_is_shown_whole() -> None:
    assert capped("a\r\nb") == "a\\r\\nb"


def test_a_value_of_64_characters_is_shown_whole() -> None:
    assert capped("a" * 64) == "a" * 64


def test_a_longer_value_is_cut_to_its_first_64_characters() -> None:
    assert capped("a" * 64 + "\r\nBcc: victim@example.com") == "a" * 64 + "…"


def test_an_unknown_charset_is_shown_cut_and_once() -> None:
    charset = "c" * 500
    with pytest.raises(LookupError) as raised:
        _ = codecs.lookup(charset)

    error = body_charset_error(charset, raised.value)

    assert str(error) == f'The body is not "{"c" * 64}…" text: no codec goes by that name.'


@pytest.mark.parametrize(
    "charset", ["SECRET-" + "c" * 249, "SECRET-\x00" + "c" * 248], ids=["unknown", "null byte"]
)
def test_an_unknown_charset_is_refused_with_no_error_of_the_codecs_behind_it(charset: str) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        check_charset(charset)

    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
    assert "c" * 65 not in str(raised.value)


def test_rendering_a_body_in_an_unknown_charset_chains_nothing_that_repeats_it() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = TextPart("hello", "SECRET-" + "c" * 249).to_string()

    assert raised.value.__cause__ is None
    assert raised.value.__context__ is None
