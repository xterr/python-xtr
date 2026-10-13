"""One piece of a response, as it arrives."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = ["ChunkInterface"]


@runtime_checkable
class ChunkInterface(Protocol):
    """A piece of a transfer, handed over by a response stream.

    A chunk is one of five things, and which one is what the four questions
    below answer: the headers have arrived (*first*), a piece of the body has
    arrived, the body is complete (*last*), the transfer has gone quiet for
    longer than it was allowed to (*timeout*), or an informational 1xx status
    came in ahead of the real one.

    Only a body chunk carries content; the other four report an event, so
    their content is empty. The offset says where the chunk's content sits in
    the body, which is what lets a reader write pieces to the right place
    without counting them itself.

    Every accessor but :meth:`get_offset` and :meth:`get_error` raises
    :class:`TransportError
    <xtr_http_client_contracts.exception.transport_error.TransportError>` when
    the transfer failed, so a reader that only ever asks what kind of chunk it
    is still finds out. :meth:`get_error` is how a reader asks instead of
    being told.
    """

    def is_timeout(self) -> bool:
        """Tell whether the transfer went quiet for longer than it was allowed to.

        A timeout chunk is not the end of the transfer: it is the stream
        saying nothing has come in, so a reader can do something else and
        keep waiting.

        Returns:
            ``True`` when this chunk is the idle timeout being reached.

        Raises:
            TransportError: When the transfer failed.
        """
        ...

    def is_first(self) -> bool:
        """Tell whether the status line and headers have just arrived.

        Returns:
            ``True`` when this chunk is the head of the response, which is
            the point from which the status and the headers can be read.

        Raises:
            TransportError: When the transfer failed, or went quiet for
                longer than it was allowed to.
        """
        ...

    def is_last(self) -> bool:
        """Tell whether the body is now complete.

        Returns:
            ``True`` when this chunk is the end of the transfer; nothing
            further arrives for this response.

        Raises:
            TransportError: When the transfer failed, or went quiet for
                longer than it was allowed to.
        """
        ...

    def get_informational_status(self) -> tuple[int, Mapping[str, Sequence[str]]] | None:
        """Return the 1xx status that just came in, with the headers it carried.

        A server may send any number of these before the real status — a 103
        listing what to fetch early, a 100 agreeing to receive a body.

        Returns:
            The status code and its headers, keyed by lowercased name, or
            ``None`` when this chunk is not an informational one.

        Raises:
            TransportError: When the transfer failed, or went quiet for
                longer than it was allowed to.
        """
        ...

    def get_content(self) -> bytes:
        """Return the piece of the body this chunk carries.

        Returns:
            The bytes that arrived, or empty bytes for any chunk that
            reports an event rather than carrying body.

        Raises:
            TransportError: When the transfer failed, or went quiet for
                longer than it was allowed to.
        """
        ...

    def get_offset(self) -> int:
        """Return where this chunk's content sits in the body.

        Returns:
            The offset in bytes from the first byte of the body.
        """
        ...

    def get_error(self) -> str | None:
        """Return what went wrong, for a reader that would rather ask than be told.

        Returns:
            What went wrong with the transfer, or ``None`` while it is going
            well.
        """
        ...
