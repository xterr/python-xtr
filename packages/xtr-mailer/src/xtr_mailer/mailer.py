"""Sends email through a transport, or queues it on a message bus."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, ClassVar, final

from typing_extensions import override

from .envelope import Envelope
from .event import MessageEvent
from .exception import TransportError
from .mailer_interface import MailerInterface
from .messenger import SendEmailMessage

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_messenger import MessageBusInterface
    from xtr_messenger.stamp import StampInterface
    from xtr_mime import RawMessage

    from .transport import TransportInterface

__all__ = ["Mailer"]


@final
class Mailer(MailerInterface):
    """Sends each email through the transport, or — given a message bus — queues it there.

    ``Mailer(transport)`` sends at once. ``Mailer(transport, bus, dispatcher)`` dispatches a
    :class:`~xtr_mailer.messenger.SendEmailMessage` on the bus instead, for its handler to send
    through the same transport, possibly in another process. Before that, a
    :class:`~xtr_mailer.event.MessageEvent` with ``queued`` set goes to the dispatcher, on a
    copy of the email and of the envelope: a listener may reject the email, so nothing is
    queued, or add the stamps it is dispatched with — but what is queued is the email as
    given, since the listeners run again on it when the transport sends it.

    When the bus handles the email in this process and the transport refuses it, the
    transport's error is raised, not the bus's report of the failed handlers.

    The bus is only ever called, so the messenger package is needed only by an application
    that hands one over.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_event_dispatcher", "_message_bus", "_transport")

    def __init__(
        self,
        transport: TransportInterface,
        message_bus: MessageBusInterface | None = None,
        event_dispatcher: EventDispatcherInterface | None = None,
    ) -> None:
        """Send through ``transport``, or queue on ``message_bus`` when given one.

        Args:
            transport: What sends the emails, now or when the bus hands them back.
            message_bus: Where emails are queued instead of sent now; ``None`` sends every
                email at once.
            event_dispatcher: Where a queued email is announced; ``None`` announces nothing
                and queues every email with no stamps. An email sent now is announced by the
                transport, on its own dispatcher.
        """
        self._transport: TransportInterface = transport
        self._message_bus: MessageBusInterface | None = message_bus
        self._event_dispatcher: EventDispatcherInterface | None = event_dispatcher

    @override
    async def send(self, message: RawMessage, envelope: Envelope | None = None) -> None:
        """Send ``message`` now, or queue it unless a listener rejects it.

        Raises:
            LogicError: ``message`` is raw bytes queued with no envelope while events are
                dispatched, or sent now with none.
            TransportError: The transport could not send the email, now or from a handler
                of the bus in this process.
        """
        bus = self._message_bus
        if bus is None:
            _ = await self._transport.send(message, envelope)
            return
        stamps: list[StampInterface] = []
        if self._event_dispatcher is not None:
            queued = copy.copy(message)
            queued_envelope = (
                copy.copy(envelope) if envelope is not None else Envelope.create(queued)
            )
            event = await self._event_dispatcher.dispatch(
                MessageEvent(queued, queued_envelope, str(self._transport), queued=True)
            )
            if event.is_rejected():
                return
            stamps = event.get_stamps()
        await _dispatch(bus, SendEmailMessage(message, envelope), stamps)


async def _dispatch(
    bus: MessageBusInterface, message: SendEmailMessage, stamps: list[StampInterface]
) -> None:
    """Dispatch ``message``; when a handler raised a transport error, raise that one.

    It is raised as the handler raised it, outside the ``except`` block: the bus's error is
    already caused by it, so chaining the two would make the chain loop.
    """
    # Only an application that hands over a bus has the messenger package installed.
    from xtr_messenger import HandlersFailedError  # noqa: PLC0415 -- see above.

    try:
        _ = await bus.dispatch(message, *stamps)
    except HandlersFailedError as error:
        refused = next((e for e in error.errors.values() if isinstance(e, TransportError)), None)
        if refused is None:
            raise
    else:
        return
    raise refused
