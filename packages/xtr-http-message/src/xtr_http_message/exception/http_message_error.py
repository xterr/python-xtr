"""The one error every failure in this package derives from."""

from __future__ import annotations

__all__ = ["HttpMessageError"]


class HttpMessageError(Exception):
    """Something went wrong building or using a message, a stream or a URI.

    Nothing raises this class itself; it exists so that an application can
    catch everything this package raises with one ``except`` clause, whichever
    of the four concrete errors reached it.
    """
