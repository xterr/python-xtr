"""Hands an event to the consumer a :class:`ConsumeRemoteEventMessage` names."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_messenger import as_message_handler

from xtr_remote_event.consumer.consumer_interface import ConsumerInterface
from xtr_remote_event.exception import LogicError

from .consume_remote_event_message import ConsumeRemoteEventMessage

if TYPE_CHECKING:
    from xtr_remote_event.consumer.consumer_locator import ConsumerLocator

__all__ = ["ConsumeRemoteEventHandler"]


@as_message_handler(ConsumeRemoteEventMessage)
@final
class ConsumeRemoteEventHandler:
    """Looks the consumer of the message's source up, and hands it the event.

    It is handed a :class:`~xtr_remote_event.consumer.ConsumerLocator`, never
    a container: the locator already answers the only question this has — who
    consumes this source — so a handler given the container could reach
    anything else the application registered as well.
    """

    __slots__ = ("_consumers",)

    def __init__(self, consumers: ConsumerLocator) -> None:
        """Hand events to the consumers in ``consumers``."""
        self._consumers = consumers

    async def __call__(self, message: ConsumeRemoteEventMessage) -> None:
        """Hand ``message.event`` to the consumer of ``message.type``.

        Raises:
            LogicError: If nothing is registered for that source, or what is
                registered consumes nothing. Both are wiring the application
                got wrong, and both are said where the event is lost rather
                than swallowed.
        """
        consumer = await self._consumers.get(message.type)
        if not isinstance(consumer, ConsumerInterface):  # pyright: ignore[reportUnnecessaryIsInstance] -- a locator over a container promises a consumer and hands over whatever was registered
            raise LogicError(
                f'The consumer "{type(consumer).__qualname__}" for message of type '
                f'"{message.type}" must implement ConsumerInterface.'
            )
        await consumer.consume(message.event)
