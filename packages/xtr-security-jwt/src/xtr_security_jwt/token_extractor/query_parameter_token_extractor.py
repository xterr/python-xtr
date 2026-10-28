"""Reads a token out of a query parameter."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .token_extractor_interface import TokenExtractorInterface

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["QueryParameterTokenExtractor"]


@final
class QueryParameterTokenExtractor(TokenExtractorInterface):
    """Reads a token out of a named query parameter.

    The extractor a link-based flow reaches for — a token in a URL — accepting
    that a query string is logged and shared more freely than a header.
    """

    __slots__ = ("_parameter_name",)

    def __init__(self, parameter_name: str = "bearer") -> None:
        """Read the token from the ``parameter_name`` query parameter."""
        self._parameter_name = parameter_name

    @override
    def extract(self, request: ServerRequestInterface) -> str | None:
        """Return the token in the query parameter, or ``None`` when it is absent."""
        value = request.get_query_params().get(self._parameter_name)
        if not isinstance(value, str) or not value:
            return None
        return value
