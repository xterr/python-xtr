"""A message: headers and a body part, with the headers sending it adds."""

from __future__ import annotations

import copy
import secrets
from typing import TYPE_CHECKING, Final

from typing_extensions import override
from xtr_clock import SystemClock

from ._engine import build_message, prepend_fields, render, to_string
from .exception import LogicError
from .header import Headers, MailboxHeader, MailboxListHeader
from .part import TextPart
from .raw_message import RawMessage

if TYPE_CHECKING:
    from collections.abc import Generator
    from typing import Self

    from xtr_clock import ClockInterface

    from ._engine import EnginePart
    from .address import Address
    from .part import AbstractPart

__all__ = ["Message"]

_NO_ORIGINATOR: Final = 'An email must have a "From" or a "Sender" header.'
_NO_RECIPIENT: Final = 'An email must have a "To", "Cc", or "Bcc" header.'


class Message(RawMessage):
    """Headers and a body part, rendered to MIME when sent.

    :meth:`get_headers` holds what the caller set; :meth:`get_prepared_headers` adds to a copy
    what sending needs — ``MIME-Version``, ``Date`` from the clock, ``Message-ID``, ``From``
    from ``Sender`` or ``Sender`` from the first of several ``From`` — and leaves ``Bcc`` out,
    which no recipient may see. A message with no body is sent with an empty text one.
    """

    def __init__(
        self,
        headers: Headers | None = None,
        body: AbstractPart | None = None,
        *,
        clock: ClockInterface | None = None,
    ) -> None:
        """Keep a copy of ``headers``, ``body`` itself, and the clock the Date is read from."""
        # A message renders itself from its headers and body: it holds no raw content.
        super().__init__(b"")
        self._headers: Headers = Headers() if headers is None else copy.copy(headers)
        self._body: AbstractPart | None = body
        self._clock: ClockInterface = SystemClock() if clock is None else clock

    def __copy__(self) -> Self:
        """Copy the headers and the body too: changing them in the copy leaves this one alone."""
        cls = type(self)
        copied = cls.__new__(cls)
        vars(copied).update(vars(self))
        return copied.set_headers(copy.copy(self._headers)).set_body(copy.copy(self._body))

    def set_body(self, body: AbstractPart | None) -> Self:
        """Replace the body part."""
        self._body = body
        return self

    def get_body(self) -> AbstractPart | None:
        """Return the body part, ``None`` unless set."""
        return self._body

    def set_headers(self, headers: Headers) -> Self:
        """Replace the headers with ``headers`` itself, not a copy."""
        self._headers = headers
        return self

    def get_headers(self) -> Headers:
        """Return the headers the caller set, which the caller may change."""
        return self._headers

    def get_prepared_headers(self) -> Headers:
        """Return a copy of the headers with what sending needs added and ``Bcc`` taken out.

        Raises:
            LogicError: There is neither a From nor a Sender, or From names no address to
                make a Message-ID from.
        """
        headers = copy.copy(self._headers)
        if not headers.has("From"):
            sender = headers.get("Sender")
            if not isinstance(sender, MailboxHeader):
                raise LogicError(_NO_ORIGINATOR)
            _ = headers.add_mailbox_list_header("From", [sender.get_address()])
        if not headers.has("MIME-Version"):
            _ = headers.add_text_header("MIME-Version", "1.0")
        if not headers.has("Date"):
            _ = headers.add_date_header("Date", self._clock.now())
        from_header = headers.get("From")
        if not headers.has("Sender") and isinstance(from_header, MailboxListHeader):
            authors = from_header.get_addresses()
            if len(authors) > 1:
                _ = headers.add_mailbox_header("Sender", authors[0])
        if not headers.has("Message-ID"):
            _ = headers.add_id_header("Message-ID", self.generate_message_id())
        headers.remove("Bcc")
        return headers

    @override
    def to_string(self) -> str:
        """Render the message: its prepared headers, then its body.

        Raises:
            LogicError: As :meth:`get_prepared_headers` does, or the body cannot be built.
            InvalidArgumentError: A body cannot be read or written as asked.
            RfcComplianceError: A header is refused.
        """
        return to_string(self._to_engine())

    @override
    def to_iterable(self) -> Generator[bytes, None, None]:
        """Render the message in the pieces the engine writes, as a mail server receives them.

        Raises:
            LogicError: As :meth:`to_string` does.
            InvalidArgumentError: As :meth:`to_string` does.
            RfcComplianceError: As :meth:`to_string` does.
        """
        yield from render(self._to_engine())

    @override
    def ensure_validity(self) -> None:
        """Check the message names a recipient and an author.

        Raises:
            LogicError: No To, Cc or Bcc names anyone, or neither From nor Sender is set.
        """
        if not any(self._header_has_body(name) for name in ("To", "Cc", "Bcc")):
            raise LogicError(_NO_RECIPIENT)
        if not any(self._header_has_body(name) for name in ("From", "Sender")):
            raise LogicError(_NO_ORIGINATOR)
        super().ensure_validity()

    def generate_message_id(self) -> str:
        """Make up a Message-ID: 32 random hex digits at the domain of the sender.

        The sender is Sender, else the first address of From; an international domain is
        written in ASCII, as the header carries it.

        Raises:
            LogicError: There is neither a From nor a Sender, or From names no address.
        """
        return f"{secrets.token_hex(16)}@{self._author().get_encoded_address().rpartition('@')[2]}"

    def _author(self) -> Address:
        match self._headers.get("Sender"), self._headers.get("From"):
            case MailboxHeader() as sender, _:
                return sender.get_address()
            case _, MailboxListHeader() as from_header:
                authors = from_header.get_addresses()
                if not authors:
                    raise LogicError('A "From" header must have at least one email address.')
                return authors[0]
            case _:
                raise LogicError(_NO_ORIGINATOR)

    def _header_has_body(self, name: str) -> bool:
        header = self._headers.get(name)
        return header is not None and bool(header.get_body())

    def _to_engine(self) -> EnginePart:
        headers = self.get_prepared_headers()
        body = self.get_body()
        if body is None:
            body = TextPart("")
        # The body's engine tree stays inside xtr-mime: the message is its one other reader.
        message = build_message((), body._to_engine())  # noqa: SLF001  # pyright: ignore[reportPrivateUsage] -- see above.
        prepend_fields(message, headers.to_array())
        return message
