"""Build a stream, from bytes, from a file, or around one already open."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from typing import BinaryIO

    from xtr_http_message_contracts.stream_interface import StreamInterface

__all__ = ["StreamFactoryInterface"]


@runtime_checkable
class StreamFactoryInterface(Protocol):
    """Makes a stream, so that a caller need not name the class that is one."""

    def create_stream(self, content: bytes = b"") -> StreamInterface:
        """Return a new stream holding ``content``.

        The stream should be backed by something temporary rather than by a
        file the caller has to clean up.

        Args:
            content: The bytes the stream starts out holding.

        Returns:
            The stream.
        """
        ...

    def create_stream_from_file(self, filename: str, mode: str = "r") -> StreamInterface:
        """Return a new stream reading a file that already exists.

        The file is opened in ``mode``, which may be any mode the host's file
        opener accepts, and ``filename`` may be anything it can open.

        Args:
            filename: The file, or the address of the stream, to read.
            mode: How to open it.

        Returns:
            The stream.

        Raises:
            RuntimeError: When the file cannot be opened.
            ValueError: When the mode is not a usable one.
        """
        ...

    def create_stream_from_resource(self, resource: BinaryIO) -> StreamInterface:
        """Return a new stream around a file object that is already open.

        The stream must be readable, and may be writable.

        Args:
            resource: The open file object to wrap.

        Returns:
            The stream.
        """
        ...
