"""Reads a token out of a query parameter."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .token_extractor_interface import TokenExtractorInterface

if TYPE_CHECKING:
    from starlette.requests import Request

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
    def extract(self, request: Request) -> str | None:
        """Return the token in the query parameter, or ``None`` when it is absent."""
        return request.query_params.get(self._parameter_name) or None
