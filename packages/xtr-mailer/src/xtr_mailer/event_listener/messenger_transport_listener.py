"""Queues an email on the message bus transports its ``X-Bus-Transport`` header names."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Final, final

from xtr_mime import Message
from xtr_mime.header import UnstructuredHeader

if TYPE_CHECKING:
    from xtr_mailer.event import MessageEvent

__all__ = ["MessengerTransportListener"]

# The characters a name is trimmed of: spaces, tabs, line breaks, NUL and vertical tab.
_TRIMMED: Final = " \t\n\r\0\x0b"


@final
class MessengerTransportListener:
    """Routes a queued email to the message bus transports its ``X-Bus-Transport`` names.

    Listen to :class:`~xtr_mailer.event.MessageEvent` with :meth:`on_message` at
    :attr:`PRIORITY`. For an email being queued, the comma-separated names of the header
    become a transport-names stamp the email is dispatched with, overriding the bus's
    routing, and the header is removed from the copy the event carries. An email sent now is
    left alone. Only an application that queues email, and so has the messenger package,
    ever has the stamp built.
    """

    #: Run at the default priority.
    PRIORITY: Final = 0

    __slots__: ClassVar[tuple[str, ...]] = ()

    def on_message(self, event: MessageEvent) -> None:
        """Stamp a queued email with the transports its header names, and drop the header."""
        if not event.is_queued():
            return
        message = event.get_message()
        if not isinstance(message, Message):
            return
        header = message.get_headers().get("X-Bus-Transport")
        if header is None:
            return
        # A queued event comes from a mailer given a bus, so the messenger package is there.
        from xtr_messenger.stamp import TransportNamesStamp  # noqa: PLC0415 -- see above.

        # The names as written: a text header's own value, any other header's as it renders.
        names = (
            header.get_body()
            if isinstance(header, UnstructuredHeader)
            else header.get_body_as_string()
        )
        event.add_stamp(TransportNamesStamp(tuple(n.strip(_TRIMMED) for n in names.split(","))))
        message.get_headers().remove("X-Bus-Transport")
