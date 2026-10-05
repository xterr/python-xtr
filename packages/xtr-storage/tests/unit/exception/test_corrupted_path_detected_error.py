from __future__ import annotations

from xtr_storage.exception import (
    CorruptedPathDetectedError,
    StorageError,
    StorageOperationFailedError,
)


def test_it_carries_the_path() -> None:
    error = CorruptedPathDetectedError("photos/a\x00.jpg")

    assert error.path == "photos/a\x00.jpg"


def test_its_message_shows_the_character_that_cannot_be_used() -> None:
    error = CorruptedPathDetectedError("photos/a\x00.jpg")

    assert str(error) == "corrupted path detected in 'photos/a\\x00.jpg'"


def test_it_is_a_storage_error_but_not_a_failed_operation() -> None:
    error = CorruptedPathDetectedError("photos/a\u200b.jpg")

    assert isinstance(error, StorageError)
    assert not isinstance(error, StorageOperationFailedError)
