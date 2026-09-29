from __future__ import annotations

from xtr_storage.exception import InvalidStreamError, StorageError


def test_it_carries_the_type_that_was_handed_in() -> None:
    error = InvalidStreamError("str")

    assert error.received == "str"


def test_its_message_names_what_was_handed_in() -> None:
    error = InvalidStreamError("str")

    assert str(error) == "a stream must be an iterable of bytes or a binary file, got str"


def test_it_is_also_a_type_error() -> None:
    error = InvalidStreamError("str")

    assert isinstance(error, StorageError)
    assert isinstance(error, TypeError)
