"""An uploaded file cannot do what is being asked of it now."""

from __future__ import annotations

from .http_message_error import HttpMessageError

__all__ = ["UploadedFileError"]


class UploadedFileError(HttpMessageError, RuntimeError):
    """An uploaded file is unusable: the upload failed, or the file is already moved.

    It derives from :class:`RuntimeError` as well as from
    :class:`~xtr_http_message.exception.http_message_error.HttpMessageError`
    because that is what the contract promises a caller: code written against
    the interfaces catches the builtin and never names this package.
    """
