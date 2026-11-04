"""Replaces who every email is delivered for and to."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar, Final, final

from xtr_mime import Address, Message

from xtr_mailer._error_text import shown
from xtr_mailer.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from xtr_mailer.event import MessageEvent

__all__ = ["EnvelopeListener"]


@final
class EnvelopeListener:
    r"""Sets the sender and the recipients every email is delivered with, whatever its headers.

    Listen to :class:`~xtr_mailer.event.MessageEvent` with :meth:`on_message` at
    :attr:`PRIORITY`, so the other listeners change the headers first. A sender replaces the
    envelope's, and becomes the ``Sender`` header of an email that has neither a Sender nor a
    From. Recipients replace the envelope's — every email of a staging environment goes to
    one inbox — except the envelope recipients an allowed pattern matches, which are kept
    after them, each once.

    An allowed pattern is a regular expression matched against the whole address, as written
    (an international domain in Unicode): ``.*@example\.com`` keeps every address at that
    domain and no other, and an alternation is anchored as a whole. The patterns are the
    application's configuration, trusted as its code is: one with nested repetition can take
    exponential time on a long address — an address is at most 254 characters.
    """

    #: Run last, after every listener that may change the headers the envelope is read from.
    PRIORITY: Final = -255

    __slots__: ClassVar[tuple[str, ...]] = ("_allowed_recipients", "_recipients", "_sender")

    def __init__(
        self,
        sender: Address | str | None = None,
        recipients: Iterable[Address | str] | None = None,
        allowed_recipients: Iterable[str] = (),
    ) -> None:
        """Deliver for ``sender`` and to ``recipients``, keeping those ``allowed_recipients`` match.

        Args:
            sender: The envelope sender of every email; ``None`` leaves each email's own. A
                string may be ``Name <address>``.
            recipients: The envelope recipients of every email; ``None`` or none at all
                leaves each email's own. A string may be ``Name <address>``.
            allowed_recipients: Regular expressions, each matched against a whole envelope
                recipient's address; one an email's recipient matches is kept as well.

        Raises:
            InvalidArgumentError: An allowed pattern is not a valid regular expression.
            RfcComplianceError: The sender or a recipient is not a valid email address.
        """
        self._sender: Address | None = None if sender is None else Address.create(sender)
        self._recipients: list[Address] | None = (
            None if recipients is None else Address.create_array(recipients)
        )
        self._allowed_recipients: list[re.Pattern[str]] = [
            _compiled(pattern) for pattern in allowed_recipients
        ]

    def on_message(self, event: MessageEvent) -> None:
        """Set the configured sender and recipients on ``event``'s envelope."""
        envelope = event.get_envelope()
        if self._sender is not None:
            envelope.set_sender(self._sender)
            message = event.get_message()
            if isinstance(message, Message):
                headers = message.get_headers()
                if not headers.has("Sender") and not headers.has("From"):
                    _ = headers.add_mailbox_header("Sender", self._sender)
        if self._recipients:
            recipients = list(self._recipients)
            for recipient in envelope.get_recipients() if self._allowed_recipients else ():
                if self._is_allowed(recipient) and recipient not in recipients:
                    recipients.append(recipient)
            envelope.set_recipients(recipients)

    def _is_allowed(self, recipient: Address) -> bool:
        address = recipient.get_address()
        return any(pattern.fullmatch(address) for pattern in self._allowed_recipients)


def _compiled(pattern: str) -> re.Pattern[str]:
    try:
        return re.compile(pattern)
    except re.error as error:
        raise InvalidArgumentError(
            f'The allowed recipient "{shown(pattern)}" is not a valid regular expression: {error}.'
        ) from None
