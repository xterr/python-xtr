"""The request was never made, because what it was asked for makes no sense."""

from __future__ import annotations

from xtr_http_client_contracts import TransportError

__all__ = ["InvalidArgumentError"]


# Both bases reach `BaseException`, which basedpyright flags as unsafe multiple inheritance.
# It is safe here: `ValueError` adds no state, so `TransportError.__init__` is the only one
# construction runs.
class InvalidArgumentError(  # pyright: ignore[reportUnsafeMultipleInheritance]
    TransportError,
    ValueError,
):
    """An option, a header, a body or a URL this client will not send.

    A method that is not uppercase, a header value carrying a newline, an
    option no client knows, a URL with no host, credentials given twice —
    every one of them is a mistake in the call rather than something that
    happened on the way, and none of them reaches a socket.

    It is a :class:`TransportError
    <xtr_http_client_contracts.exception.transport_error.TransportError>`
    because the contract says a client refuses what it cannot honour by
    raising that, so one ``except`` covers both "this request cannot be made"
    and "this request failed". It is also a :class:`ValueError`, which is what
    a mistake in an argument is in Python, so code that already guards its
    inputs keeps working.
    """
