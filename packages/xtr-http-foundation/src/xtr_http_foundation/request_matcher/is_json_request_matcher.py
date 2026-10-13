"""A matcher over whether the body of a request reads as JSON."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast, final

from typing_extensions import override

from xtr_http_foundation.request_matcher_interface import RequestMatcherInterface

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["IsJsonRequestMatcher"]


@final
class IsJsonRequestMatcher(RequestMatcherInterface):
    """Claims a request whose body reads as JSON.

    The body itself is read, not the ``Content-Type`` header: a sender that
    announces nothing still sent JSON, and one that announces JSON and sent
    something else did not. Any JSON value counts — an object, an array, a
    number, a string — so this is the rule for "a body worth decoding" rather
    than for a shape.

    A body nobody can read is not claimed, and neither is one that is not even
    text: both are the same answer as a body that is not JSON, since neither can
    be decoded.
    """

    __slots__ = ()

    @override
    async def matches(self, request: ServerRequestInterface) -> bool:
        """Tell whether the body of ``request`` reads as JSON.

        The whole body is read, from its first byte: a stream another matcher
        has already read is rewound first, so the order matchers are chained in
        changes nothing.
        """
        try:
            body = await request.get_body().get_contents()
        except RuntimeError:
            return False

        try:
            _ = cast("object", json.loads(body))
        except ValueError:
            return False

        return True
