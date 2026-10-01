"""What reads a bearer access token out of a request."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from fastapi.security.base import SecurityBase
    from starlette.requests import Request

__all__ = ["AccessTokenExtractorInterface"]


@runtime_checkable
class AccessTokenExtractorInterface(Protocol):
    """Reads the token string from a request, and names the scheme it read it by.

    An extractor knows where a token lives — an ``Authorization`` header, a
    query parameter, a form field — and returns it as a string, or ``None``
    when the request carries none. :meth:`scheme` returns the FastAPI security
    object the extractor is built on, so the same object both parses the
    request and describes the scheme in the generated OpenAPI.
    """

    async def extract_access_token(self, request: Request) -> str | None:
        """Return the token in ``request``, or ``None`` when there is none."""
        ...

    def scheme(self) -> SecurityBase:
        """Return the FastAPI security object this extractor parses and documents by."""
        ...
