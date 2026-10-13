"""A method, URL or option the client cannot use; raised before anything is sent."""

from __future__ import annotations

from .transport_error import TransportError

__all__ = ["InvalidArgumentError"]


# Both bases reach `BaseException`, which basedpyright flags as unsafe multiple inheritance.
# It is safe here: `ValueError` adds no state, so `TransportError.__init__` is the only one
# construction runs.
class InvalidArgumentError(  # pyright: ignore[reportUnsafeMultipleInheritance]
    TransportError,
    ValueError,
):
    """The request was refused before it was sent, for something it asked for.

    An unknown option name, an option whose value the client cannot honour, a
    method or URL it cannot make a request with, or a body given both with the
    request and as an option. Nothing reached the network, so there is no
    response, and the same call with a corrected argument would go through.

    Also a :class:`ValueError`, so code that already guards the arguments it
    passes with ``except ValueError`` keeps working without learning a new
    exception.
    """
