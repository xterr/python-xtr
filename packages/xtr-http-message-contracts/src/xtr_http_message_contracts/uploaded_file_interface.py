"""A file that came in with a request."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .stream_interface import StreamInterface

__all__ = ["UploadedFileInterface"]


@runtime_checkable
class UploadedFileInterface(Protocol):
    """One uploaded file, as a value: what arrived, how much of it, and from where.

    Instances are immutable — nothing here returns a changed copy, and nothing
    changes the file in place except :meth:`move_to`, which is the one
    operation that consumes it.
    """

    def get_stream(self) -> StreamInterface:
        """Return the contents of the file as a stream.

        Reading it as a stream is what lets the file be copied anywhere a
        stream can be written to.

        Returns:
            The contents of the uploaded file.

        Raises:
            RuntimeError: When there is no stream to be had — :meth:`move_to`
                having already taken the file away, among other reasons.
        """
        ...

    def move_to(self, target_path: str) -> None:
        """Move the file to ``target_path``, consuming it.

        The path may be absolute or relative; a relative one is resolved the
        way the file system calls of the host resolve one.

        Whatever held the file is gone once this returns, which is why calling
        it a second time is an error rather than a second move.

        To put the file somewhere a path cannot name, read :meth:`get_stream`
        and write that where it needs to go.

        Args:
            target_path: Where to move the file to.

        Raises:
            ValueError: When the target path is not a usable one.
            RuntimeError: When the move fails, or when the file has already
                been moved.
        """
        ...

    def get_size(self) -> int | None:
        """Return the size of the file in bytes.

        The size reported should be the one recorded as the file arrived,
        counted from what was actually received.

        Returns:
            The size in bytes, or ``None`` when it is not known.
        """
        ...

    def get_error(self) -> int:
        """Return how the upload went.

        The value is one of
        :class:`~xtr_http_message_contracts.upload_error.UploadError`, and it
        is :attr:`~xtr_http_message_contracts.upload_error.UploadError.OK`
        when the file arrived whole. The value recorded as the file arrived is
        the one that should come back.

        Returns:
            The outcome of the upload.
        """
        ...

    def get_client_filename(self) -> str | None:
        """Return the file name the client sent.

        Do not trust it. It is whatever the client chose to send, and a client
        may well have chosen it to break something.

        The name recorded as the file arrived is the one that should come
        back.

        Returns:
            The file name the client sent, or ``None`` when it sent none.
        """
        ...

    def get_client_media_type(self) -> str | None:
        """Return the media type the client sent.

        Do not trust it either, and for the same reason.

        The media type recorded as the file arrived is the one that should
        come back.

        Returns:
            The media type the client sent, or ``None`` when it sent none.
        """
        ...
