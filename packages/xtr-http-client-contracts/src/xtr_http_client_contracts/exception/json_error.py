"""A body that is not the JSON object to_array() promises."""

from __future__ import annotations

from .decoding_error import DecodingError

__all__ = ["JsonError"]


class JsonError(DecodingError):
    """The body is JSON, but not the object :meth:`HttpResponseInterface.to_array` promises.

    A JSON array, string, number or ``null`` where an object was asked for. The
    body was read in full and parsed, so the failure is the shape of the payload,
    not the transfer.

    Also a :class:`DecodingError`, so code that already catches a body it could
    not decode keeps catching this one.
    """
