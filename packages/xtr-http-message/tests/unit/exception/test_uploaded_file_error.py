from __future__ import annotations

from xtr_http_message import HttpMessageError, UploadedFileError


def test_it_carries_the_message_it_was_raised_with() -> None:
    assert str(UploadedFileError("already moved")) == "already moved"


def test_it_is_an_http_message_error() -> None:
    assert isinstance(UploadedFileError("x"), HttpMessageError)


def test_it_is_also_a_runtime_error() -> None:
    assert isinstance(UploadedFileError("x"), RuntimeError)
