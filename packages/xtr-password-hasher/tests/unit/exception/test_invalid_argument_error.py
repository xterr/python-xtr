from __future__ import annotations

from xtr_password_hasher import InvalidArgumentError


def test_it_records_the_reason() -> None:
    error = InvalidArgumentError("the bcrypt cost must be between 4 and 31")

    assert error.reason == "the bcrypt cost must be between 4 and 31"
    assert str(error) == "the bcrypt cost must be between 4 and 31"


def test_it_is_a_value_error() -> None:
    assert issubclass(InvalidArgumentError, ValueError)
