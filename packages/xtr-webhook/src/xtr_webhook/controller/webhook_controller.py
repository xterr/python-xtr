"""What answers a webhook: read it, hand on what it carried, reply to its sender."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Final, TypeVar, final

from xtr_http_message_contracts import ResponseInterface
from xtr_remote_event import RemoteEvent
from xtr_remote_event.messenger import ConsumeRemoteEventMessage

from xtr_webhook.exception import RejectWebhookError

from ._built_parsers import BuiltParsers

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_messenger import MessageBusInterface
    from xtr_service_contracts import ServiceProviderInterface

    from xtr_webhook.client import RequestParserInterface

__all__ = ["WebhookController"]

R = TypeVar("R", bound=ResponseInterface)

_NOT_FOUND: Final = 404
_PLAIN_TEXT: Final = "text/plain; charset=utf-8"
_NO_PARSER: Final = "No webhook parser found for the type given in the URL."
_UNPARSABLE: Final = "Unable to parse the webhook payload."


def _as_plain_text(
    response: R,
    status_code: int,
    reason: str,
    headers: Mapping[str, str],
) -> R:
    """Return ``response`` carrying ``reason`` as text under ``status_code``.

    ``headers`` is applied last, so a refusal that needs a header of its own —
    a challenge under a 401 — sets it, and may override the content type if
    its own answer is not text.
    """
    answered = response.with_status(status_code).with_header("Content-Type", _PLAIN_TEXT)
    for name, value in headers.items():
        answered = answered.with_header(name, value)
    _ = answered.get_body().write(reason.encode())

    return answered


@final
class WebhookController:
    """Receives every incoming webhook, whoever sent it.

    One endpoint for every subscriber, told apart by the type in the URL: that
    type picks the parser that reads the webhook and the secret it is checked
    against, so adding a subscriber is configuration rather than another route.

    What the endpoint itself does is deliberately small. Reading a webhook is
    the parser's, handling what it carried is the consumer's, and in between
    this does the one thing neither can: answer the sender now, and leave the
    work for a worker. A sender waiting on a handler is a sender that times
    out and sends the webhook again.
    """

    __slots__ = ("_bus", "_parsers", "_secrets")

    def __init__(
        self,
        parsers: ServiceProviderInterface[RequestParserInterface]
        | Mapping[str, RequestParserInterface],
        secrets: Mapping[str, str],
        bus: MessageBusInterface,
    ) -> None:
        """Receive webhooks for the types ``parsers`` speaks for.

        Args:
            parsers: The parser reading each type, by type. A container's
                locator builds each on the first webhook for it; a mapping of
                parsers built by hand is wrapped in one that behaves the same.
            secrets: What each type's webhooks are checked against, by type.
                Copied, so what a type is checked against cannot change under
                a request. A type with no entry is checked against an empty
                secret, which a parser verifying anything refuses.
            bus: Where an event that was read is handed on.
        """
        self._parsers: ServiceProviderInterface[RequestParserInterface] = (
            BuiltParsers(parsers) if isinstance(parsers, Mapping) else parsers
        )
        self._secrets = dict(secrets)
        self._bus = bus

    async def index_action(
        self,
        event_type: str,
        request: ServerRequestInterface,
        response: R,
    ) -> R:
        """Read the webhook that arrived for ``event_type``, and answer its sender.

        Every answer but the last is a refusal, and each says as little as the
        sender needs: a type nothing speaks for is a 404, because from the
        sender's side that URL does not exist; a webhook the parser would not
        take is whatever the parser answers; a webhook it read nothing out of
        is refused as unparsable rather than accepted and dropped.

        Anything else raised on the way out — a bus with nothing to handle the
        event above all — is left to propagate. The sender then gets a 5xx and
        sends the webhook again, which is the only outcome that does not lose
        what it carried.

        Args:
            event_type: The type in the URL: which subscriber this is for.
            request: The webhook as it arrived.
            response: The response to answer with, to fill in and give back.

        Returns:
            ``response`` with the answer on it.
        """
        if not self._parsers.has(event_type):
            return _as_plain_text(response, _NOT_FOUND, _NO_PARSER, {})

        parser = await self._parsers.get(event_type)

        try:
            events = await parser.parse(request, self._secrets.get(event_type, ""))
        except RejectWebhookError as refused:
            return _as_plain_text(response, refused.status_code, str(refused), refused.headers)

        if not events:
            return parser.create_rejected_response(_UNPARSABLE, request, response)

        for event in [events] if isinstance(events, RemoteEvent) else events:
            _ = await self._bus.dispatch(ConsumeRemoteEventMessage(event_type, event))

        return parser.create_successful_response(request, response)
