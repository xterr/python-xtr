"""Reads a token out of a cookie."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .token_extractor_interface import TokenExtractorInterface

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["CookieTokenExtractor"]


@final
class CookieTokenExtractor(TokenExtractorInterface):
    """Reads a token out of a named cookie.

    The extractor a browser-facing deployment reaches for, keeping the token out
    of JavaScript's reach in an http-only cookie.
    """

    __slots__ = ("_name",)

    def __init__(self, name: str = "BEARER") -> None:
        """Read the token from the ``name`` cookie."""
        self._name = name

    @override
    def extract(self, request: ServerRequestInterface) -> str | None:
        """Return the token in the cookie, or ``None`` when it is absent."""
        return request.get_cookie_params().get(self._name) or None
