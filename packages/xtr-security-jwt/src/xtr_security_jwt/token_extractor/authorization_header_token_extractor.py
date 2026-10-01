"""Reads a token out of an authorization header."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .token_extractor_interface import TokenExtractorInterface

if TYPE_CHECKING:
    from starlette.requests import Request

__all__ = ["AuthorizationHeaderTokenExtractor"]


@final
class AuthorizationHeaderTokenExtractor(TokenExtractorInterface):
    """Reads a token out of a request header, after a scheme prefix.

    The default extractor: the token travels in ``Authorization: Bearer <token>``.
    With a prefix, the header must be exactly the prefix, a space and the token;
    with an empty prefix, the whole header value is the token.
    """

    __slots__ = ("_name", "_prefix")

    def __init__(self, prefix: str = "Bearer", name: str = "Authorization") -> None:
        """Read from the ``name`` header, expecting the ``prefix`` scheme word."""
        self._prefix = prefix
        self._name = name

    @override
    def extract(self, request: Request) -> str | None:
        """Return the token after the prefix in the header, or ``None``."""
        header = request.headers.get(self._name)
        if not header:
            return None
        if not self._prefix:
            return header
        parts = header.split(" ")
        expected = 2
        if len(parts) != expected or parts[0].lower() != self._prefix.lower():
            return None
        return parts[1]
