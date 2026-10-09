"""A file that came in with a request."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal, final

from typing_extensions import override
from xtr_http_message_contracts import StreamInterface, UploadedFileInterface, UploadError

from .exception import InvalidArgumentError, UploadedFileError
from .stream import Stream

if TYPE_CHECKING:
    from typing import BinaryIO

__all__ = ["UploadedFile"]

# How much of a stream-backed upload is held in memory while it is copied.
_CHUNK = 1_048_576

_NOT_AN_ERROR = "Upload file error status must be one of the UploadError values"
_NOTHING_ARRIVED = "Cannot retrieve stream due to upload error"
_ALREADY_MOVED = "Cannot retrieve stream after it has already been moved"
_NO_PATH = "Invalid path provided for move operation; must be a non-empty string"
_NO_SOURCE = "Invalid stream or file provided for UploadedFile"


@final
class UploadedFile(UploadedFileInterface):
    """One uploaded file: what arrived, how much of it, and from where.

    Two kinds arrive. One is already a stream — a form parser handed it over —
    and comes back as that same stream. The other is a path on disk, which is
    opened only when the file is read, so that a request carrying twenty files
    nobody looks at opens none of them.

    ```python
    from xtr_http_message import Stream, UploadedFile

    upload = UploadedFile(Stream.create(b"hello"), 5, 0, "greeting.txt", "text/plain")
    assert bytes(upload.get_stream()) == b"hello"
    ```

    An upload that did not go through carries nothing: the error says why, and
    reading or moving it is refused. Moving it is what consumes it, so a
    second move is refused too.
    """

    __slots__ = (
        "_client_filename",
        "_client_media_type",
        "_error",
        "_moved",
        "_size",
        "_source",
    )

    def __init__(
        self,
        stream_or_file: StreamInterface | str | BinaryIO,
        size: int | None,
        error: int,
        client_filename: str | None = None,
        client_media_type: str | None = None,
    ) -> None:
        """Record an uploaded file.

        Args:
            stream_or_file: What arrived: a stream over the contents, a path
                on disk, or an open binary file object. Ignored when ``error``
                says the upload did not go through.
            size: The size in bytes as the file arrived, or ``None`` when it
                was not counted.
            error: How the upload went, as one of
                :class:`~xtr_http_message_contracts.upload_error.UploadError`.
            client_filename: The file name the client sent, if any. Do not
                trust it.
            client_media_type: The media type the client sent, if any. Do not
                trust that either.

        Raises:
            InvalidArgumentError: When ``error`` is not one of the upload
                outcomes, or when the upload went through with nothing to
                read it from.
        """
        try:
            self._error: UploadError = UploadError(error)
        except ValueError as invalid:
            raise InvalidArgumentError(_NOT_AN_ERROR) from invalid

        self._size: int | None = size
        self._client_filename: str | None = client_filename
        self._client_media_type: str | None = client_media_type
        self._moved: bool = False
        self._source: StreamInterface | str | None = None

        if self._error != UploadError.OK:
            # Nothing arrived, so there is nothing to keep: the error is the
            # whole of what this file has to say.
            return

        if isinstance(stream_or_file, str):
            if stream_or_file == "":
                raise InvalidArgumentError(_NO_SOURCE)
            self._source = stream_or_file
        elif isinstance(stream_or_file, StreamInterface):
            self._source = stream_or_file
        else:
            self._source = Stream.create(stream_or_file)

    @override
    def get_stream(self) -> StreamInterface:
        """Return the contents of the file as a stream.

        A file backed by a path is opened here, every time it is asked for; a
        file that arrived as a stream comes back as that same stream.

        Returns:
            The contents of the uploaded file.

        Raises:
            UploadedFileError: When the upload did not go through, when the
                file has already been moved, or when the path it is on cannot
                be opened.
        """
        source = self._active_source()
        if not isinstance(source, str):
            return source

        return Stream.create(_open(source, "rb"))

    @override
    def move_to(self, target_path: str) -> None:
        """Move the file to ``target_path``, consuming it.

        A file on disk is moved as it is. One that arrived as a stream is
        copied a mebibyte at a time, so that a large upload never has to fit
        in memory.

        Args:
            target_path: Where to move the file to, absolute or relative.

        Raises:
            InvalidArgumentError: When the target path is empty.
            UploadedFileError: When the upload did not go through, when the
                file has already been moved, or when the move fails.
        """
        source = self._active_source()

        if target_path == "":
            raise InvalidArgumentError(_NO_PATH)

        if isinstance(source, str):
            try:
                _ = Path(source).replace(target_path)
            except OSError as failure:
                message = f'Uploaded file could not be moved to "{target_path}": {failure}'
                raise UploadedFileError(message) from failure
        else:
            _copy_into(source, target_path)

        self._moved = True

    @override
    def get_size(self) -> int | None:
        """Return the size of the file in bytes.

        Returns:
            The size recorded as the file arrived, or ``None`` when it was not
            counted.
        """
        return self._size

    @override
    def get_error(self) -> int:
        """Return how the upload went.

        Returns:
            The outcome, which is
            :attr:`~xtr_http_message_contracts.upload_error.UploadError.OK`
            when the file arrived whole.
        """
        return self._error

    @override
    def get_client_filename(self) -> str | None:
        """Return the file name the client sent.

        Returns:
            The name the client sent, or ``None`` when it sent none. Do not
            trust it: a client may well have chosen it to break something.
        """
        return self._client_filename

    @override
    def get_client_media_type(self) -> str | None:
        """Return the media type the client sent.

        Returns:
            The media type the client sent, or ``None`` when it sent none. Do
            not trust it either, and for the same reason.
        """
        return self._client_media_type

    def _active_source(self) -> StreamInterface | str:
        """Return what the file is to be read from, refusing it when there is none.

        Returns:
            The stream the file arrived as, or the path it is on.

        Raises:
            UploadedFileError: When the upload did not go through — the
                constructor keeps a source only for one that did — or when the
                file has already been moved away.
        """
        source = self._source
        if source is None:
            raise UploadedFileError(_NOTHING_ARRIVED)

        if self._moved:
            raise UploadedFileError(_ALREADY_MOVED)

        return source


def _open(path: str, mode: Literal["rb", "wb"]) -> BinaryIO:
    """Open a path for an uploaded file, saying which path failed when it will not open.

    Args:
        path: The path to open.
        mode: How to open it.

    Returns:
        The open file object.

    Raises:
        UploadedFileError: When the path cannot be opened.
    """
    try:
        return Path(path).open(mode)
    except OSError as failure:
        message = f'The file "{path}" cannot be opened: {failure}'
        raise UploadedFileError(message) from failure


def _copy_into(source: StreamInterface, target_path: str) -> None:
    """Copy a stream into a file, a mebibyte at a time.

    Args:
        source: The stream to copy, rewound first when it can be.
        target_path: The path to write it to.

    Raises:
        UploadedFileError: When the target path cannot be opened.
    """
    if source.is_seekable():
        source.rewind()

    with _open(target_path, "wb") as file:
        destination = Stream(file)
        while not source.eof():
            if destination.write(source.read(_CHUNK)) == 0:
                break
