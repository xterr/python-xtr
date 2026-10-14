"""A parser that takes a header at its word, so the abstract parser can be exercised.

Nothing here verifies anything worth trusting: the point is to have the smallest
subclass that fills in the two hooks :class:`AbstractRequestParser` leaves open, so
the tests can watch what the base class does around them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_http_foundation import (
    ChainRequestMatcher,
    IsJsonRequestMatcher,
    MethodRequestMatcher,
    RequestMatcherInterface,
)
from xtr_remote_event import RemoteEvent

from xtr_webhook.client import AbstractRequestParser
from xtr_webhook.exception import RejectWebhookError

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["SecretHeaderRequestParser"]


@final
class SecretHeaderRequestParser(AbstractRequestParser):
    """Accepts a JSON ``POST`` whose ``X-Secret`` header repeats the secret.

    The matcher is a real chain of two shared matchers, so a request the parser
    was never meant to see — a ``GET``, a form post — is turned away by the base
    class before :meth:`do_parse` is reached.
    """

    __slots__ = ()

    @override
    def get_request_matcher(self) -> RequestMatcherInterface:
        """Claim only a ``POST`` whose body reads as JSON."""
        return ChainRequestMatcher([MethodRequestMatcher("POST"), IsJsonRequestMatcher()])

    @override
    async def do_parse(self, request: ServerRequestInterface, secret: str) -> RemoteEvent | None:
        """Check the header against the secret and read the body into an event."""
        if secret != request.get_header_line("X-Secret"):
            raise RejectWebhookError(406, "Invalid secret.")

        return RemoteEvent("parsed", "the-id", await self.read_json(request))
