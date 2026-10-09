"""Everything this package raises, under one base class.

The contract names two builtins — :class:`ValueError` for an argument that
cannot be what it is being used as, :class:`RuntimeError` for an operation
that cannot be carried out now — so each error here derives from the builtin
the contract named *and* from
:class:`~xtr_http_message.exception.http_message_error.HttpMessageError`. A
caller written against the interfaces catches the builtin; one that chose this
implementation can catch the base class instead and get only its failures.
"""

from __future__ import annotations

from .http_message_error import HttpMessageError
from .invalid_argument_error import InvalidArgumentError
from .stream_error import StreamError
from .uploaded_file_error import UploadedFileError

__all__ = [
    "HttpMessageError",
    "InvalidArgumentError",
    "StreamError",
    "UploadedFileError",
]
