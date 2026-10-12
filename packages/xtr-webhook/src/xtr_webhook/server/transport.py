"""The delivery itself: build the request, post it, judge the answer."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_webhook.exception import DeliveryError, LogicError

from .outgoing_request import OutgoingRequest
from .transport_interface import TransportInterface

if TYPE_CHECKING:
    from xtr_remote_event import RemoteEvent

    from xtr_webhook.subscriber import Subscriber

    from .http_sender_interface import HttpSenderInterface
    from .request_configurator_interface import RequestConfiguratorInterface

__all__ = ["Transport"]

_ACCEPTED = range(200, 300)
"""The answers that count as delivered: success, nothing else."""


@final
class Transport(TransportInterface):
    """Runs the configurator chain over a fresh request and posts what it built.

    The order is fixed — headers, body, signer — because the signer reads back
    what the other two wrote: the body it signs and the timestamp it covers must
    already be there. The request is fresh per send so nothing of one delivery
    leaks into the next.

    Any answer outside 200-299 raises: a delivery runs inside a message handler,
    and the error is what makes the bus retry it and, once the attempts are
    spent, keep the message instead of dropping it. A redirect counts as refused
    too — following one would carry a signed body to an address nobody vetted.
    """

    __slots__ = ("_body", "_headers", "_sender", "_signer")

    def __init__(
        self,
        sender: HttpSenderInterface,
        headers: RequestConfiguratorInterface,
        body: RequestConfiguratorInterface,
        signer: RequestConfiguratorInterface,
    ) -> None:
        """Configure what builds each part, and what carries the result.

        Args:
            sender: What posts the built bytes.
            headers: The step that writes the headers naming the event.
            body: The step that writes the payload into the body.
            signer: The step that signs what the other two wrote. It runs last.
        """
        self._sender = sender
        self._headers = headers
        self._body = body
        self._signer = signer

    @override
    async def send(self, subscriber: Subscriber, event: RemoteEvent) -> None:
        """Deliver ``event`` to ``subscriber``.

        Args:
            subscriber: Where the webhook goes, and the secret it is signed
                with.
            event: What to deliver.

        Raises:
            LogicError: When the chain never wrote a body. A chain that builds
                nothing to send is a wiring mistake, caught before anything
                leaves.
            DeliveryError: When the receiver answered with a status outside
                200-299.
        """
        request = OutgoingRequest()
        self._headers.configure(event, subscriber.secret, request)
        self._body.configure(event, subscriber.secret, request)
        self._signer.configure(event, subscriber.secret, request)

        body = request.body
        if body is None:
            raise LogicError("The body must be set.")

        status_code = await self._sender.post(subscriber.url, request.headers, body)

        if status_code not in _ACCEPTED:
            raise DeliveryError(status_code, subscriber.url)
