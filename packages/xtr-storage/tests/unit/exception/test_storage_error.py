from __future__ import annotations

from xtr_storage.exception import StorageError


def test_it_is_an_exception() -> None:
    assert issubclass(StorageError, Exception)


def test_it_carries_the_message_it_is_given() -> None:
    assert str(StorageError("the backend went away")) == "the backend went away"
