"""An extractor that reads a bearer token from a query parameter."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .access_token_extractor_interface import AccessTokenExtractorInterface

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["QueryAccessTokenExtractor"]


@final
class QueryAccessTokenExtractor(AccessTokenExtractorInterface):
    """Reads a token from a query parameter, ``access_token`` by default.

    A request without the parameter reads as ``None``. Passing a bearer token
    in the URL is discouraged by RFC 6750, but some clients can send it no
    other way; the extractor exists for them.

    Attributes:
        parameter_name: The query parameter the token is read from.
    """

    __slots__ = ("_parameter_name",)

    def __init__(self, parameter_name: str = "access_token") -> None:
        """Build the extractor for the ``parameter_name`` query parameter."""
        self._parameter_name = parameter_name

    @override
    async def extract_access_token(self, request: ServerRequestInterface) -> str | None:
        """Return the token in the query parameter, or ``None`` when it is absent.

        A name the query answers with anything other than one text value —
        the contract lets a repeated or nested name answer structure — reads
        as no token: a bearer token is one string, and anything else in its
        place is a malformed request rather than a credential.
        """
        value = request.get_query_params().get(self._parameter_name)
        return value if isinstance(value, str) else None
