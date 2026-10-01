"""Reads a token spread across several cookies and rejoins it."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .token_extractor_interface import TokenExtractorInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from starlette.requests import Request

__all__ = ["SplitCookieExtractor"]


@final
class SplitCookieExtractor(TokenExtractorInterface):
    """Reads a token split across several named cookies and joins them with dots.

    A token stored in parts — header, payload, signature in separate cookies, so
    the signature cookie alone can be http-only — is rebuilt here. Every named
    cookie must be present, or nothing is returned.
    """

    __slots__ = ("_cookies",)

    def __init__(self, cookies: Sequence[str]) -> None:
        """Read the token from the ``cookies``, in order."""
        self._cookies = tuple(cookies)

    @override
    def extract(self, request: Request) -> str | None:
        """Return the token rejoined from its cookies, or ``None`` when one is absent."""
        if not self._cookies:
            return None
        parts: list[str] = []
        for name in self._cookies:
            value = request.cookies.get(name)
            if not value:
                return None
            parts.append(value)
        return ".".join(parts)
