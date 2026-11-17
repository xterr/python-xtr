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
    from xtr_serializer import SerializerInterface
    from xtr_service_contracts import ServiceProviderInterface

    from xtr_webhook.client import RequestParserInterface
    from xtr_webhook.client.webhook_id_store_interface import WebhookIdStoreInterface

__all__ = ["WebhookController"]

R = TypeVar("R", bound=ResponseInterface)

_NOT_FOUND: Final = 404
_PLAIN_TEXT: Final = "text/plain; charset=utf-8"
_NO_PARSER: Final = "No webhook parser found for the type given in the URL."
_UNPARSABLE: Final = "Unable to parse the webhook payload."
_WIRE_FORMAT: Final = "json"


async def _as_plain_text(
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
    _ = await answered.get_body().write(reason.encode())

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

    __slots__ = ("_bus", "_id_store", "_id_ttl", "_parsers", "_secrets", "_serializer")

    def __init__(  # noqa: PLR0913 -- the endpoint's collaborators, the id store optional past them
        self,
        parsers: ServiceProviderInterface[RequestParserInterface]
        | Mapping[str, RequestParserInterface],
        secrets: Mapping[str, str],
        bus: MessageBusInterface,
        serializer: SerializerInterface,
        *,
        id_store: WebhookIdStoreInterface | None = None,
        id_ttl: int = 86_400,
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
            serializer: What writes each message as a bus writing its messages does, so a
                message it would refuse is found before any message of the webhook is
                dispatched.
            id_store: Where the ids of the events already taken are remembered,
                keyed by type and id. An event whose id it already remembers is
                acknowledged and not handed on again: a sender retries a webhook
                whose answer it never received, and refusing the retry would have
                it retry forever. ``None`` hands on every event.
            id_ttl: How many seconds an id is remembered — as long as a sender
                may retry.
        """
        self._parsers: ServiceProviderInterface[RequestParserInterface] = (
            BuiltParsers(parsers) if isinstance(parsers, Mapping) else parsers
        )
        self._secrets = dict(secrets)
        self._bus = bus
        self._serializer = serializer
        self._id_store = id_store
        self._id_ttl = id_ttl

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

        Every event's message is written before the first is dispatched, so a
        message the bus could not write — a payload value JSON cannot carry
        exactly — fails the webhook with none of its events dispatched: the
        sender's retry would otherwise queue the ones before it a second time.

        Args:
            event_type: The type in the URL: which subscriber this is for.
            request: The webhook as it arrived.
            response: The response to answer with, to fill in and give back.

        Returns:
            ``response`` with the answer on it.
        """
        if not self._parsers.has(event_type):
            return await _as_plain_text(response, _NOT_FOUND, _NO_PARSER, {})

        parser = await self._parsers.get(event_type)

        try:
            events = await parser.parse(request, self._secrets.get(event_type, ""))
        except RejectWebhookError as refused:
            return await _as_plain_text(
                response, refused.status_code, str(refused), refused.headers
            )

        if not events:
            return await parser.create_rejected_response(_UNPARSABLE, request, response)

        messages = [
            ConsumeRemoteEventMessage(event_type, event)
            for event in ([events] if isinstance(events, RemoteEvent) else events)
        ]
        for message in messages:
            _ = self._serializer.serialize(message, _WIRE_FORMAT, type_=ConsumeRemoteEventMessage)
        for message in messages:
            key = f"{event_type}:{message.event.id}"
            if self._id_store is not None and not await self._id_store.remember(key, self._id_ttl):
                continue
            try:
                _ = await self._bus.dispatch(message)
            except BaseException:
                # Not handed on, so the sender's retry must be handled, not acknowledged.
                if self._id_store is not None:
                    await self._id_store.forget(key)
                raise

        return await parser.create_successful_response(request, response)
