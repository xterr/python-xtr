"""What reads a token out of a request."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["TokenExtractorInterface"]


@runtime_checkable
class TokenExtractorInterface(Protocol):
    """Reads a token out of a request, or reports that there is none.

    Each extractor knows one place a token may travel — a header, a cookie, a
    query parameter — and returns the token found there, or ``None`` when the
    request carries none in that place.
    """

    def extract(self, request: ServerRequestInterface) -> str | None:
        """Return the token in ``request``, or ``None`` when there is none."""
        ...
