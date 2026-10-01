from __future__ import annotations

import pytest

from xtr_password_hasher import MAX_PASSWORD_LENGTH, InvalidPasswordError
from xtr_password_hasher.hasher._password_length import ensure_within_length, is_within_length


def test_it_accepts_a_password_at_the_limit() -> None:
    assert is_within_length("a" * MAX_PASSWORD_LENGTH)
    ensure_within_length("a" * MAX_PASSWORD_LENGTH)


def test_it_reports_an_over_long_password() -> None:
    assert not is_within_length("a" * (MAX_PASSWORD_LENGTH + 1))


def test_ensure_raises_on_an_over_long_password() -> None:
    with pytest.raises(InvalidPasswordError) as caught:
        ensure_within_length("a" * (MAX_PASSWORD_LENGTH + 1))

    assert caught.value.length == MAX_PASSWORD_LENGTH + 1
    assert caught.value.max_length == MAX_PASSWORD_LENGTH


def test_it_counts_utf8_bytes_not_characters() -> None:
    two_byte = "é"
    at_limit = two_byte * (MAX_PASSWORD_LENGTH // 2)

    assert len(at_limit) == MAX_PASSWORD_LENGTH // 2
    assert is_within_length(at_limit)
    assert not is_within_length(at_limit + two_byte)


def test_ensure_reports_the_byte_length_for_multibyte_input() -> None:
    two_byte = "é"
    over = two_byte * (MAX_PASSWORD_LENGTH // 2 + 1)

    with pytest.raises(InvalidPasswordError) as caught:
        ensure_within_length(over)

    assert caught.value.length == MAX_PASSWORD_LENGTH + 2
