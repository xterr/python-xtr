"""A matcher that claims a request whose body announces itself as JSON."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .request_matcher_interface import RequestMatcherInterface

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["IsJsonRequestMatcher"]

_JSON = "application/json"
_SUFFIX = "+json"


@final
class IsJsonRequestMatcher(RequestMatcherInterface):
    """Claims a request whose ``Content-Type`` names a JSON media type.

    That is ``application/json``, or any type whose subtype ends in ``+json`` —
    ``application/vnd.acme.event+json`` and the rest of the structured-syntax
    family, which senders use to name their own payload and still say it is
    JSON.

    Everything after the first ``;`` is a parameter — ``charset``, ``version``
    — and says nothing about the syntax, so it is dropped before comparing. The
    media type itself is compared without case, as HTTP defines it.
    """

    __slots__ = ()

    @override
    def matches(self, request: ServerRequestInterface) -> bool:
        """Tell whether the request announces a JSON body.

        A request carrying no ``Content-Type`` at all is refused: a body of
        unannounced syntax is not one to guess at.
        """
        media_type = request.get_header_line("Content-Type").split(";", 1)[0].strip().lower()

        return media_type == _JSON or media_type.endswith(_SUFFIX)
