"""The envelope a message's own headers give, read from them when it is asked for."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

from typing_extensions import override
from xtr_mime import MailboxHeader, MailboxListHeader, PathHeader

from .envelope import Envelope
from .exception import LogicError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from xtr_mime import Address, Headers, Message

__all__ = ["DelayedEnvelope"]


@final
class DelayedEnvelope(Envelope):
    """An envelope that reads the sender and recipients from a message until they are set.

    Reading late lets a listener change the message's headers after the envelope was made and
    still be heard. The recipients read keep their names, as the headers give them; the ones
    set lose them, as in any envelope.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_message", "_recipients_set", "_sender_set")

    def __init__(self, message: Message) -> None:  # pyright: ignore[reportMissingSuperCall] -- there is no sender nor recipient to check yet: both are read from the message when asked for.
        """Read the envelope from ``message``'s headers, each time it is asked for."""
        self._message: Message = message
        self._recipients: list[Address] = []
        self._sender_set: bool = False
        self._recipients_set: bool = False

    @override
    def set_sender(self, sender: Address) -> None:
        """Replace the sender; the headers are no longer read for it.

        Raises:
            InvalidArgumentError: ``sender`` is not an address or has a non-ASCII local part.
        """
        super().set_sender(sender)
        self._sender_set = True

    @override
    def get_sender(self) -> Address:
        """Return the sender set, else the one the headers give now.

        Raises:
            LogicError: The headers name no sender: no Sender, no Return-Path, no author.
            InvalidArgumentError: The sender they name has a non-ASCII local part.
        """
        if not self._sender_set:
            super().set_sender(_sender_of(self._message.get_headers()))
        return super().get_sender()

    @override
    def set_recipients(self, recipients: Iterable[Address]) -> None:
        """Replace the recipients; the headers are no longer read for them.

        Raises:
            InvalidArgumentError: There is no recipient, or one is not an address.
        """
        super().set_recipients(recipients)
        self._recipients_set = True

    @override
    def get_recipients(self) -> list[Address]:
        """Return the recipients set, else every address To, Cc and Bcc give now, in order."""
        if self._recipients_set:
            return super().get_recipients()
        headers = self._message.get_headers()
        return [
            address
            for name in ("To", "Cc", "Bcc")
            for header in headers.all(name)
            if isinstance(header, MailboxListHeader)
            for address in header.get_addresses()
        ]


def _sender_of(headers: Headers) -> Address:
    match headers.get("Sender"), headers.get("Return-Path"), headers.get("From"):
        case MailboxHeader() as sender, _, _:
            return sender.get_address()
        case _, PathHeader() as return_path, _:
            return return_path.get_address()
        case _, _, MailboxListHeader() as authors if authors.get_addresses():
            return authors.get_addresses()[0]
        case _:
            raise LogicError("Unable to determine the sender of the message.")
