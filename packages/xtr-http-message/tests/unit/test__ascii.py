from __future__ import annotations

import pytest

from xtr_http_message._ascii import lower


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param("ABC", "abc", id="letters"),
        pytest.param("aBc", "abc", id="mixed"),
        pytest.param("abc", "abc", id="already-lower"),
        pytest.param("", "", id="empty"),
        pytest.param("A1-_.Z", "a1-_.z", id="letters-among-others"),
    ],
)
def test_an_ascii_letter_is_lowercased(text: str, expected: str) -> None:
    assert lower(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        # The Kelvin sign and the Ångström sign, which `str.lower` folds onto
        # an ASCII letter: doing that here would make two names that differ
        # match each other.
        pytest.param("\u212a", id="kelvin-sign"),
        pytest.param("\u212b", id="angstrom-sign"),
        # A letter outside ASCII is not ours to recase.
        pytest.param("ΟΥΤΟΠΊΑ", id="greek"),
        pytest.param("É", id="latin-with-an-accent"),
        pytest.param("İ", id="dotted-capital-i"),
    ],
)
def test_a_character_outside_ascii_is_left_exactly_as_it_was(text: str) -> None:
    assert lower(text) == text
