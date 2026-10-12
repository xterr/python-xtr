"""Everything a parser of incoming webhooks does the same way as every other."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, TypeVar

import msgspec
from typing_extensions import override
from xtr_http_message_contracts import ResponseInterface

from xtr_webhook.exception import RejectWebhookError

from .request_parser_interface import RequestParserInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_remote_event import RemoteEvent

    from .request_matcher_interface import RequestMatcherInterface

__all__ = ["AbstractRequestParser"]

R = TypeVar("R", bound=ResponseInterface)

_MALFORMED = "Request body is malformed."
_PLAIN_TEXT = "text/plain; charset=utf-8"
_UNACCEPTABLE = 406
_ACCEPTED = 202


class AbstractRequestParser(RequestParserInterface, ABC):
    """A parser with everything but the two things that differ per sender filled in.

    What is left to a subclass is which requests are its sender's
    (:meth:`get_request_matcher`) and how to check and read one
    (:meth:`do_parse`). Everything around those is the same for every sender,
    and wrong in the same way when each parser writes it again: the shape check
    has to run before the body is touched, an unreadable body has to come out as
    a refusal rather than as a 500, and both answers have to be the ones the
    sender's side is waiting for.

    ```python
    class AcmeRequestParser(AbstractRequestParser):
        def get_request_matcher(self) -> RequestMatcherInterface:
            return ChainRequestMatcher([MethodRequestMatcher("POST"), IsJsonRequestMatcher()])

        async def do_parse(self, request, secret):
            payload = self.read_json(request)
            return RemoteEvent("acme", str(payload["id"]), payload)
    ```
    """

    @override
    async def parse(
        self,
        request: ServerRequestInterface,
        secret: str,
    ) -> RemoteEvent | Sequence[RemoteEvent] | None:
        """Check the shape of the request, then hand it to :meth:`do_parse`.

        A body that will not decode is the sender's doing, not this
        application's, so it comes back as a refusal the endpoint can answer
        with rather than as an error the endpoint would report as its own
        fault.

        Args:
            request: The request that arrived.
            secret: What the sender's signature is checked against.

        Returns:
            Whatever :meth:`do_parse` read out of the request.

        Raises:
            RejectWebhookError: When the request is not one this parser
                claims, when its body will not decode, or when
                :meth:`do_parse` refuses it.
        """
        self.validate(request)

        try:
            return await self.do_parse(request, secret)
        except (msgspec.DecodeError, UnicodeDecodeError) as unreadable:
            raise RejectWebhookError(_UNACCEPTABLE, _MALFORMED) from unreadable

    @override
    def create_successful_response(self, request: ServerRequestInterface, response: R) -> R:
        """Answer a webhook that was read with 202 and nothing else.

        The sender is told the webhook was taken, not what became of it: the
        events it carried are handled after the answer has gone, so there is
        nothing yet to report and nothing the sender could do with it.

        Args:
            request: The request the endpoint received. Unused here; a parser
                whose sender wants something echoed back overrides this.
            response: The response the endpoint built.

        Returns:
            ``response`` with the status set, its body left empty.
        """
        del request

        return response.with_status(_ACCEPTED)

    @override
    def create_rejected_response(
        self,
        reason: str,
        request: ServerRequestInterface,
        response: R,
    ) -> R:
        """Answer a refused webhook with 406 and the reason as plain text.

        406 says the request was understood and still not acceptable, which is
        what a wrong signature, a stale timestamp and an unreadable payload all
        amount to from the sender's side. The reason goes in the body as text
        because that is the one thing a sender's log is likely to keep.

        Args:
            reason: What to tell the sender.
            request: The request the endpoint received. Unused here.
            response: The response the endpoint built.

        Returns:
            ``response`` with the status, the content type and the reason on
            it.
        """
        del request

        refused = response.with_status(_UNACCEPTABLE).with_header("Content-Type", _PLAIN_TEXT)
        _ = refused.get_body().write(reason.encode())

        return refused

    @abstractmethod
    def get_request_matcher(self) -> RequestMatcherInterface:
        """Return what decides whether a request is this parser's sender's.

        Returns:
            The matcher every request is put through before it is read.
        """

    @abstractmethod
    async def do_parse(
        self,
        request: ServerRequestInterface,
        secret: str,
    ) -> RemoteEvent | Sequence[RemoteEvent] | None:
        """Check that the request is genuine and read the events out of it.

        The request has already been through :meth:`get_request_matcher`, so
        its shape is not in question here. Whatever the sender's protocol asks
        for is: comparing a signature over the raw body against a header, in
        constant time, and refusing a timestamp outside the window it allows.

        Args:
            request: The request that arrived.
            secret: What the sender's signature is checked against.

        Returns:
            The event the request carried, every event when it carried
            several, or ``None`` when it is one to accept and ignore.

        Raises:
            RejectWebhookError: On any failure to verify the request.
        """

    def validate(self, request: ServerRequestInterface) -> None:
        """Refuse a request this parser's matcher does not claim.

        Args:
            request: The request that arrived.

        Raises:
            RejectWebhookError: When the matcher does not claim the request.
        """
        if not self.get_request_matcher().matches(request):
            raise RejectWebhookError(_UNACCEPTABLE, "Request does not match.")

    def read_body(self, request: ServerRequestInterface) -> bytes:
        """Return the body of the request, whole, from its first byte.

        A signature is made over exactly the bytes that arrived, and whatever
        read the body before this — a framework logging it, a matcher looking
        at it — left the cursor wherever it stopped. So the stream is rewound
        first, where it can be.

        Args:
            request: The request that arrived.

        Returns:
            Every byte of the body.
        """
        body = request.get_body()
        if body.is_seekable():
            body.rewind()

        return body.get_contents()

    def read_json(self, request: ServerRequestInterface) -> dict[str, object]:
        """Return the body of the request read as a JSON object.

        Args:
            request: The request that arrived.

        Returns:
            The object the body decoded to, its values left as they came.

        Raises:
            RejectWebhookError: When the body is valid JSON but not an object
                — an array or a bare value is not a webhook payload.
            msgspec.DecodeError: When the body is not JSON at all. Raised
                rather than refused here, so that :meth:`parse` turns it into
                the same refusal wherever in a subclass it came from.
        """
        try:
            return msgspec.json.decode(self.read_body(request), type=dict[str, object])
        except msgspec.ValidationError as not_an_object:
            raise RejectWebhookError(_UNACCEPTABLE, _MALFORMED) from not_an_object
