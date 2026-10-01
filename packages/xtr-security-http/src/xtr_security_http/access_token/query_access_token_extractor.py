"""An extractor that reads a bearer token from a query parameter."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from fastapi.security import APIKeyQuery
from typing_extensions import override

from .access_token_extractor_interface import AccessTokenExtractorInterface

if TYPE_CHECKING:
    from fastapi.security.base import SecurityBase
    from starlette.requests import Request

__all__ = ["QueryAccessTokenExtractor"]


@final
class QueryAccessTokenExtractor(AccessTokenExtractorInterface):
    """Reads a token from a query parameter, ``access_token`` by default.

    Built on FastAPI's :class:`~fastapi.security.APIKeyQuery` with
    ``auto_error=False``, so a request without the parameter reads as ``None``.
    Passing a bearer token in the URL is discouraged by RFC 6750, but some
    clients can send it no other way; the extractor exists for them.

    Attributes:
        parameter_name: The query parameter the token is read from.
    """

    __slots__ = ("_parameter_name", "_query")

    def __init__(self, parameter_name: str = "access_token") -> None:
        """Build the extractor for the ``parameter_name`` query parameter."""
        self._parameter_name = parameter_name
        self._query = APIKeyQuery(
            name=parameter_name,
            auto_error=False,
            scheme_name=parameter_name,
        )

    @override
    async def extract_access_token(self, request: Request) -> str | None:
        """Return the token in the query parameter, or ``None`` when it is absent."""
        return await self._query(request)

    @override
    def scheme(self) -> SecurityBase:
        """Return the query-parameter scheme this extractor reads and documents by."""
        return self._query
