"""The sender and recipients an email is delivered with, apart from what its headers say."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from xtr_mime import Address, Message

from ._error_text import shown
from .exception import InvalidArgumentError, LogicError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from xtr_mime import RawMessage

__all__ = ["Envelope"]


class Envelope:
    """Who an email is delivered for and to: the SMTP ``MAIL FROM`` and ``RCPT TO``.

    The envelope is what a server delivers by, whatever the headers show: a Bcc recipient is in
    the envelope and in no header, and a bounce goes to the envelope's sender. The recipients
    are bare addresses, their names dropped — a server has no use for them.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_recipients", "_sender")

    def __init__(self, sender: Address, recipients: Iterable[Address]) -> None:
        """Keep ``sender`` and ``recipients``, once checked.

        Raises:
            InvalidArgumentError: The sender is not an address or has a non-ASCII local part,
                or there is no recipient, or a recipient is not an address.
        """
        self._recipients: list[Address] = []
        self.set_sender(sender)
        self.set_recipients(recipients)

    @staticmethod
    def create(message: RawMessage) -> Envelope:
        """Return the envelope ``message``'s own headers give, read when it is asked for.

        The sender is the Sender header, else the Return-Path, else the first author; the
        recipients are every address of To, Cc and Bcc, group members included. Each is read
        from the headers as they are when asked for, until it is set.

        Raises:
            LogicError: ``message`` is raw bytes, which have no headers to read.
        """
        if not isinstance(message, Message):
            raise LogicError("Cannot send a RawMessage instance without an explicit Envelope.")
        # The delayed envelope derives from this class: importing it at the top would be circular.
        from ._delayed_envelope import DelayedEnvelope  # noqa: PLC0415 -- see above.

        return DelayedEnvelope(message)

    def set_sender(self, sender: Address) -> None:
        """Replace the sender, who a bounce goes back to.

        Its local part must be ASCII: a bounce must reach it through any server, whether or
        not that server speaks SMTPUTF8.

        Raises:
            InvalidArgumentError: ``sender`` is not an address or has a non-ASCII local part.
        """
        # A caller without a type checker may hand anything over.
        if not isinstance(sender, Address):  # pyright: ignore[reportUnnecessaryIsInstance] -- see above.
            raise InvalidArgumentError(  # pyright: ignore[reportUnreachable] -- as above.
                'The sender must be an instance of "xtr_mime.Address" '
                f'(got "{type(sender).__name__}").'
            )
        local_part, at, _ = sender.get_address().partition("@")
        if not (local_part and at and local_part.isascii()):
            raise InvalidArgumentError(
                f'Invalid sender "{shown(sender.get_address())}": non-ASCII characters not '
                "supported in local-part of email."
            )
        self._sender: Address = sender

    def get_sender(self) -> Address:
        """Return the sender, with its name; ``MAIL FROM`` takes its bare address."""
        return self._sender

    def set_recipients(self, recipients: Iterable[Address]) -> None:
        """Replace the recipients with their bare addresses, names dropped.

        Raises:
            InvalidArgumentError: There is no recipient, or one is not an address.
        """
        bare: list[Address] = []
        for recipient in recipients:
            # A caller without a type checker may hand anything over.
            if not isinstance(recipient, Address):  # pyright: ignore[reportUnnecessaryIsInstance] -- see above.
                raise InvalidArgumentError(
                    'A recipient must be an instance of "xtr_mime.Address" '
                    f'(got "{type(recipient).__name__}").'
                )
            bare.append(Address(recipient.get_address()))
        if not bare:
            raise InvalidArgumentError("An envelope must have at least one recipient.")
        self._recipients = bare

    def get_recipients(self) -> list[Address]:
        """Return the recipients, in order; changing the list leaves the envelope as it is."""
        return list(self._recipients)

    def any_address_has_unicode_localpart(self) -> bool:
        """Tell whether the sender or a recipient has a non-ASCII local part.

        Such an address can only be sent through a server speaking SMTPUTF8 (RFC 6531); a
        non-ASCII domain alone is written in punycode and needs nothing special.
        """
        return self.get_sender().has_unicode_localpart() or any(
            recipient.has_unicode_localpart() for recipient in self.get_recipients()
        )
