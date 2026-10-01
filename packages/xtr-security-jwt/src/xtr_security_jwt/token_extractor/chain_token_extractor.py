"""Tries several token extractors in turn, returning the first token found."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

from .token_extractor_interface import TokenExtractorInterface

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from starlette.requests import Request

__all__ = ["ChainTokenExtractor"]


@final
class ChainTokenExtractor(TokenExtractorInterface):
    """Runs each of several extractors in order, returning the first token found.

    The one the firewall is given: a deployment that accepts a token in a header
    or a cookie lists both, and the first place a token turns up wins.
    """

    __slots__ = ("_extractors",)

    def __init__(self, extractors: Sequence[TokenExtractorInterface]) -> None:
        """Record the extractors to try, in order.

        Raises:
            InvalidArgumentError: When no extractor is given, which would find no
                token ever.
        """
        if not extractors:
            raise InvalidArgumentError("A chain token extractor needs at least one extractor.")
        self._extractors = tuple(extractors)

    @override
    def extract(self, request: Request) -> str | None:
        """Return the first token any extractor finds, or ``None`` when none do."""
        for extractor in self._extractors:
            token = extractor.extract(request)
            if token is not None:
                return token
        return None

    def __iter__(self) -> Iterator[TokenExtractorInterface]:
        """Iterate the extractors this chain tries, in order."""
        return iter(self._extractors)
