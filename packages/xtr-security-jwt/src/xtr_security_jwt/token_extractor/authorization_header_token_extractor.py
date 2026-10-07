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
    With a prefix, the header must be the prefix and then the token, separated by
    any run of whitespace; with an empty prefix, the whole header value is the
    token. A header that names the scheme and nothing after it carries no token.
    """

    __slots__ = ("_name", "_prefix")

    def __init__(self, prefix: str = "Bearer", name: str = "Authorization") -> None:
        """Read from the ``name`` header, expecting the ``prefix`` scheme word."""
        self._prefix = prefix
        self._name = name

    @override
    def extract(self, request: Request) -> str | None:
        """Return the token after the prefix in the header, or ``None``.

        The header is read with its surrounding whitespace dropped, and the
        scheme is split from the token on the first run of whitespace, so a
        header padded by a client — or one that puts two spaces after the scheme
        — still yields the token it carries. A scheme with nothing readable after
        it is no token at all, rather than an empty one the verifier would refuse
        later.
        """
        header = request.headers.get(self._name)
        if not header:
            return None
        value = header.strip()
        if not self._prefix:
            return value or None
        parts = value.split(maxsplit=1)
        expected = 2
        if len(parts) != expected or parts[0].lower() != self._prefix.lower():
            return None
        return parts[1].strip() or None
