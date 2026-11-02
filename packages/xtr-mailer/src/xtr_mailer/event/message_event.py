"""An email about to be sent, or queued to be."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

from xtr_event_dispatcher_contracts import Event

from xtr_mailer.exception import LogicError

if TYPE_CHECKING:
    from xtr_messenger.stamp import StampInterface
    from xtr_mime import RawMessage

    from xtr_mailer.envelope import Envelope

__all__ = ["MessageEvent"]


@final
class MessageEvent(Event):
    """An email is about to be sent — or handed to a message bus to be sent later.

    Dispatched by a transport before it sends, and by the mailer when it queues instead, so a
    listener sees every email whichever way it leaves. A listener may replace the message or
    the envelope, reject the email so it is not sent at all, or — for a queued email only —
    add the message bus stamps it is dispatched with.
    """

    __slots__: ClassVar[tuple[str, ...]] = (
        "_envelope",
        "_message",
        "_queued",
        "_rejected",
        "_stamps",
        "_transport",
    )

    def __init__(
        self,
        message: RawMessage,
        envelope: Envelope,
        transport: str,
        queued: bool = False,
    ) -> None:
        """Describe ``message`` going to ``transport``, queued rather than sent now or not."""
        self._message: RawMessage = message
        self._envelope: Envelope = envelope
        self._transport: str = transport
        self._queued: bool = queued
        self._rejected: bool = False
        self._stamps: list[StampInterface] = []

    def get_message(self) -> RawMessage:
        """Return the email as the listeners so far left it."""
        return self._message

    def set_message(self, message: RawMessage) -> None:
        """Replace the email the transport or the message bus gets."""
        self._message = message

    def get_envelope(self) -> Envelope:
        """Return the envelope as the listeners so far left it."""
        return self._envelope

    def set_envelope(self, envelope: Envelope) -> None:
        """Replace the envelope the email is delivered with."""
        self._envelope = envelope

    def get_transport(self) -> str:
        """Return the name of the transport the email goes to."""
        return self._transport

    def is_queued(self) -> bool:
        """Tell whether the email is handed to a message bus instead of sent now."""
        return self._queued

    def is_rejected(self) -> bool:
        """Tell whether a listener rejected the email."""
        return self._rejected

    def reject(self) -> None:
        """Keep the email from being sent, and skip the listeners after this one."""
        self._rejected = True
        self.stop_propagation()

    def add_stamp(self, stamp: StampInterface) -> None:
        """Add a stamp the queued email is dispatched on the message bus with.

        Raises:
            LogicError: The email is sent now, not queued.
        """
        self._ensure_queued("add_stamp")
        self._stamps.append(stamp)

    def get_stamps(self) -> list[StampInterface]:
        """Return the stamps added so far, in order; changing the list leaves the event alone.

        Raises:
            LogicError: The email is sent now, not queued.
        """
        self._ensure_queued("get_stamps")
        return list(self._stamps)

    def _ensure_queued(self, method: str) -> None:
        if not self._queued:
            raise LogicError(
                f'Cannot call "MessageEvent.{method}()" on a message that is not meant to be '
                "queued."
            )
