"""A body that was read as JSON and is not."""

from __future__ import annotations

from xtr_http_client_contracts import DecodingError

__all__ = ["JsonError"]


class JsonError(DecodingError):
    """What reading a response as JSON raises when the bytes do not allow it.

    An empty body, bytes that are not JSON at all, or JSON that decodes to
    something other than an object when an object is what the caller asked
    for. The transfer finished; this is about the payload.

    It adds nothing to :class:`DecodingError
    <xtr_http_client_contracts.exception.decoding_error.DecodingError>` but a
    name, so a caller that cares only about JSON can say so, while one that
    catches the contract's error keeps catching this.
    """
