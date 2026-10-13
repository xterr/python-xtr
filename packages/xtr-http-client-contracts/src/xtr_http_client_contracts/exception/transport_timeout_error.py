"""Nothing arrived in time."""

from __future__ import annotations

from .transport_error import TransportError

__all__ = ["TransportTimeoutError"]


# Both bases reach `BaseException`, which basedpyright flags as unsafe multiple inheritance.
# It is safe here: `TimeoutError` adds no state, so `TransportError.__init__` is the only one
# construction runs.
class TransportTimeoutError(  # pyright: ignore[reportUnsafeMultipleInheritance]
    TransportError,
    TimeoutError,
):
    """The transfer went quiet for longer than it was allowed to.

    Raised when the idle timeout passes with nothing coming in, when the
    whole transfer outlasts ``max_duration``, or when connecting outlasts
    ``max_connect_duration``.

    Also a :class:`TimeoutError`, which is what every async library in the
    standard library raises and what ``anyio`` cancel scopes turn a deadline
    into, so code that already gives up on a timeout keeps working without
    learning a new exception.
    """
