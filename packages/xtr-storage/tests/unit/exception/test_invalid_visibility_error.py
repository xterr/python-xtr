from __future__ import annotations

from xtr_storage.exception import InvalidVisibilityError, StorageError


def test_it_carries_the_value_that_was_refused() -> None:
    error = InvalidVisibilityError("world")

    assert error.visibility == "world"


def test_its_message_names_the_value() -> None:
    error = InvalidVisibilityError("world")

    assert str(error) == "'world' is not a known visibility"


def test_it_is_also_a_value_error() -> None:
    error = InvalidVisibilityError("world")

    assert isinstance(error, StorageError)
    assert isinstance(error, ValueError)
