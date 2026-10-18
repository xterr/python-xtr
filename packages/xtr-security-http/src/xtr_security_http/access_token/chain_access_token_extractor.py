"""An extractor that tries several extractors in order."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

from .access_token_extractor_interface import AccessTokenExtractorInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["ChainAccessTokenExtractor"]


@final
class ChainAccessTokenExtractor(AccessTokenExtractorInterface):
    """Returns the first token any of its extractors finds.

    Tries each extractor in turn and returns the first non-``None`` token, so a
    firewall can accept a token from a header or a query parameter without
    caring which the client used.
    """

    __slots__ = ("_extractors",)

    def __init__(self, extractors: Sequence[AccessTokenExtractorInterface]) -> None:
        """Record the extractors to try, in order.

        Raises:
            InvalidArgumentError: When no extractor is given, which would find
                no token ever.
        """
        if not extractors:
            raise InvalidArgumentError(
                "A chain access-token extractor needs at least one extractor."
            )
        self._extractors = tuple(extractors)

    @override
    async def extract_access_token(self, request: ServerRequestInterface) -> str | None:
        """Return the first token any extractor finds, or ``None`` when none do."""
        for extractor in self._extractors:
            token = await extractor.extract_access_token(request)
            if token is not None:
                return token
        return None
