"""What reads a bearer access token out of a request."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["AccessTokenExtractorInterface"]


@runtime_checkable
class AccessTokenExtractorInterface(Protocol):
    """Reads the token string from a request.

    An extractor knows where a token lives — an ``Authorization`` header, a
    query parameter, a form field — and returns it as a string, or ``None``
    when the request carries none.
    """

    async def extract_access_token(self, request: ServerRequestInterface) -> str | None:
        """Return the token in ``request``, or ``None`` when there is none."""
        ...
