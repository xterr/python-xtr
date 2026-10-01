from __future__ import annotations

from xtr_password_hasher import InvalidPasswordError


def test_it_records_the_byte_length_and_the_limit() -> None:
    error = InvalidPasswordError(5000, 4096)

    assert error.length == 5000
    assert error.max_length == 4096


def test_its_message_names_the_byte_length_and_the_limit() -> None:
    error = InvalidPasswordError(5000, 4096)

    assert "5000 bytes" in str(error)
    assert "4096" in str(error)


def test_it_is_a_value_error() -> None:
    assert issubclass(InvalidPasswordError, ValueError)
