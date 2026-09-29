from __future__ import annotations

from xtr_storage.exception import InvalidArgumentError, StorageError


def test_it_carries_the_reason() -> None:
    error = InvalidArgumentError("a prefix cannot be empty")

    assert error.reason == "a prefix cannot be empty"


def test_its_message_is_the_reason() -> None:
    error = InvalidArgumentError("a prefix cannot be empty")

    assert str(error) == "a prefix cannot be empty"


def test_it_is_also_a_value_error() -> None:
    error = InvalidArgumentError("a prefix cannot be empty")

    assert isinstance(error, StorageError)
    assert isinstance(error, ValueError)
