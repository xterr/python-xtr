"""The transfer went quiet, or failed outright."""

from __future__ import annotations

from typing import TYPE_CHECKING, NoReturn, final

from xtr_http_client.exception import TransportError, TransportTimeoutError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = ["ErrorChunk"]


@final
class ErrorChunk:
    """The one chunk that tells a reader rather than letting it ask.

    Two things end up here, told apart by what it was built with. A plain
    message is the idle timeout being reached: the transfer is alive, nothing
    has come in for as long as it was allowed to, and a reader that asks
    :meth:`is_timeout` is told so without being interrupted — which is what
    lets it do something else and keep waiting. An exception is a transfer
    that is over, and every question about it raises.

    Either way, only :meth:`is_timeout` can answer quietly. Every other
    accessor raises, so a reader that never asks about the error still finds
    out about it from the question it did ask — the idle timeout as
    :class:`TransportTimeoutError
    <xtr_http_client_contracts.exception.transport_timeout_error.TransportTimeoutError>`,
    a failure as :class:`TransportError
    <xtr_http_client_contracts.exception.transport_error.TransportError>` with
    whatever broke it as the cause. :meth:`get_offset` and :meth:`get_error`
    are the two that never raise, for a reader that would rather ask.

    :meth:`did_throw` is how the stream that made the chunk learns whether the
    reader was ever told: a chunk nobody asked anything of is an error on its
    way to being swallowed, and the stream raises it itself instead.
    """

    __slots__ = ("_did_throw", "_error", "_message", "_offset", "_timeout")

    def __init__(self, offset: int, error: str | BaseException, timeout: float = 0.0) -> None:
        """Record where the body stopped, what stopped it, and how long it was given.

        Args:
            offset: Where in the body the transfer got to.
            error: The idle timeout as a message, or the exception that ended
                the transfer. An exception is kept whole, so the error this
                chunk raises carries it as its cause.
            timeout: How long the transfer was allowed to stay quiet, recorded
                so a reader can report it without reading it back out of the
                message.
        """
        self._offset = offset
        self._timeout = timeout
        self._did_throw = False
        self._error = error if isinstance(error, BaseException) else None
        self._message = str(error)

    @property
    def timeout(self) -> float:
        """How long the transfer was allowed to stay quiet, in seconds."""
        return self._timeout

    def is_timeout(self) -> bool:
        """Tell whether the transfer went quiet for longer than it was allowed to.

        Returns:
            ``True`` when this chunk is the idle timeout being reached.

        Raises:
            TransportError: When the transfer failed instead, since then there
                is nothing left to wait for.
        """
        self._did_throw = True
        if self._error is not None:
            raise TransportError(self._message) from self._error
        return True

    def is_first(self) -> bool:
        """Raise, since no head arrives after this.

        Raises:
            TransportError: Always.
        """
        self._report()

    def is_last(self) -> bool:
        """Raise, since the body is not complete and will not become so.

        Raises:
            TransportError: Always.
        """
        self._report()

    def get_informational_status(self) -> tuple[int, Mapping[str, Sequence[str]]] | None:
        """Raise, since no status came in.

        Raises:
            TransportError: Always.
        """
        self._report()

    def get_content(self) -> bytes:
        """Raise, since no bytes came in.

        Raises:
            TransportError: Always.
        """
        self._report()

    def get_offset(self) -> int:
        """Return where in the body the transfer got to."""
        return self._offset

    def get_error(self) -> str:
        """Return what went wrong, for a reader that would rather ask than be told."""
        return self._message

    def did_throw(self) -> bool:
        """Tell whether a reader has been told about the error yet.

        An idle timeout answered by :meth:`is_timeout` counts as telling: the
        reader asked what this chunk was and got the truth, so nothing is
        being swallowed.
        """
        return self._did_throw

    def _report(self) -> NoReturn:
        self._did_throw = True
        if self._error is not None:
            raise TransportError(self._message) from self._error
        raise TransportTimeoutError(self._message)
