"""What was given, shown in an error message without breaking it."""

from __future__ import annotations

import pytest

from xtr_mailer._error_text import shown


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("fabièn@example.com", "fabièn@example.com", id="printable"),
        pytest.param("a\r\nb", "a\\r\\nb", id="line-break"),
        pytest.param("a\x00b", "a\\x00b", id="null"),
        pytest.param("a\udcffb", "a\\udcffb", id="surrogate"),
        pytest.param('a"b', 'a"b', id="quote"),
        pytest.param("a'b", "a'b", id="apostrophe"),
        pytest.param("é" * 64, "é" * 64, id="at-the-limit"),
        pytest.param("é" * 65, "é" * 64 + "…", id="over-the-limit"),
    ],
)
def test_a_value_is_shown_escaped_and_cut_short(value: str, expected: str) -> None:
    assert shown(value) == expected
