"""An email built step by step: addresses, subject, priority, bodies and attachments."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, BinaryIO, ClassVar, TypeAlias

from typing_extensions import override

from ._email_body import NO_BODY, assemble_body
from ._email_headers import (
    add_addresses,
    get_address,
    get_addresses,
    priority_value,
    read_priority,
    set_addresses,
)
from .address import Address
from .exception import LogicError
from .message import Message
from .part import DataPart, File

if TYPE_CHECKING:
    from collections.abc import Iterable
    from os import PathLike
    from typing import Self

    from xtr_clock import ClockInterface

    from .header import Headers
    from .part import AbstractPart

__all__ = ["Email"]

Body: TypeAlias = "str | bytes | BinaryIO"
"""A text or HTML body: a string, bytes in its charset, or a binary file read when needed."""


class Email(Message):
    """An email built with chained calls, its body put together from what was given.

    The body is a text part, an HTML part or both (``multipart/alternative``); attachments the
    HTML shows through ``cid:`` sit next to it (``multipart/related``) and the others after it
    (``multipart/mixed``). It is put together when first asked for and kept until the text,
    the HTML or the attachments change, so a signature and the message sent see the same
    boundaries. A body set with :meth:`set_body` is sent as it is instead.
    """

    PRIORITY_HIGHEST: ClassVar[int] = 1
    PRIORITY_HIGH: ClassVar[int] = 2
    PRIORITY_NORMAL: ClassVar[int] = 3
    PRIORITY_LOW: ClassVar[int] = 4
    PRIORITY_LOWEST: ClassVar[int] = 5

    def __init__(
        self,
        headers: Headers | None = None,
        body: AbstractPart | None = None,
        *,
        clock: ClockInterface | None = None,
    ) -> None:
        """Start with a copy of ``headers`` and, if given, a body sent as it is."""
        super().__init__(headers, body, clock=clock)
        self._text: Body | None = None
        self._text_charset: str | None = None
        self._html: Body | None = None
        self._html_charset: str | None = None
        self._attachments: list[DataPart] = []
        self._cached_body: AbstractPart | None = None

    @override
    def __copy__(self) -> Self:
        """Copy the headers, the body and the list of attachments: the parts are shared."""
        copied = super().__copy__()
        copied._attachments = list(self._attachments)  # noqa: SLF001 -- the copy is an Email too.
        return copied

    def subject(self, subject: str) -> Self:
        """Set the Subject."""
        self.get_headers().set_header_body("text", "Subject", subject)
        return self

    def get_subject(self) -> str | None:
        """Return the Subject, ``None`` unless set."""
        subject = self.get_headers().get_header_body("Subject")
        return subject if isinstance(subject, str) else None

    def date(self, date_time: datetime) -> Self:
        """Set the Date; sending sets it from the clock otherwise."""
        self.get_headers().set_header_body("date", "Date", date_time)
        return self

    def get_date(self) -> datetime | None:
        """Return the Date, ``None`` unless set."""
        date_time = self.get_headers().get_header_body("Date")
        return date_time if isinstance(date_time, datetime) else None

    def return_path(self, address: Address | str) -> Self:
        """Set the Return-Path, where a bounce goes."""
        self.get_headers().set_header_body("path", "Return-Path", Address.create(address))
        return self

    def get_return_path(self) -> Address | None:
        """Return the Return-Path, ``None`` unless set."""
        return get_address(self.get_headers(), "Return-Path")

    def sender(self, address: Address | str) -> Self:
        """Set the Sender, who sent the email on behalf of its authors."""
        self.get_headers().set_header_body("mailbox", "Sender", Address.create(address))
        return self

    def get_sender(self) -> Address | None:
        """Return the Sender, ``None`` unless set."""
        return get_address(self.get_headers(), "Sender")

    def add_from(self, *addresses: Address | str) -> Self:
        """Add authors after those already set."""
        return self._add_addresses("From", addresses)

    def from_(self, *addresses: Address | str) -> Self:
        """Set the authors, replacing any set.

        Raises:
            LogicError: No address is given.
        """
        if not addresses:
            raise LogicError('"from_()" must be called with at least one address.')
        return self._set_addresses("From", addresses)

    def get_from(self) -> list[Address]:
        """Return the authors, group members included."""
        return get_addresses(self.get_headers(), "From")

    def add_reply_to(self, *addresses: Address | str) -> Self:
        """Add addresses replies go to."""
        return self._add_addresses("Reply-To", addresses)

    def reply_to(self, *addresses: Address | str) -> Self:
        """Set the addresses replies go to, replacing any set."""
        return self._set_addresses("Reply-To", addresses)

    def get_reply_to(self) -> list[Address]:
        """Return the addresses replies go to."""
        return get_addresses(self.get_headers(), "Reply-To")

    def add_to(self, *addresses: Address | str) -> Self:
        """Add recipients."""
        return self._add_addresses("To", addresses)

    def to(self, *addresses: Address | str) -> Self:
        """Set the recipients, replacing any set."""
        return self._set_addresses("To", addresses)

    def get_to(self) -> list[Address]:
        """Return the recipients, group members included."""
        return get_addresses(self.get_headers(), "To")

    def add_cc(self, *addresses: Address | str) -> Self:
        """Add recipients of a copy."""
        return self._add_addresses("Cc", addresses)

    def cc(self, *addresses: Address | str) -> Self:
        """Set the recipients of a copy, replacing any set."""
        return self._set_addresses("Cc", addresses)

    def get_cc(self) -> list[Address]:
        """Return the recipients of a copy."""
        return get_addresses(self.get_headers(), "Cc")

    def add_bcc(self, *addresses: Address | str) -> Self:
        """Add hidden recipients."""
        return self._add_addresses("Bcc", addresses)

    def bcc(self, *addresses: Address | str) -> Self:
        """Set the hidden recipients, replacing any set; no recipient sees them."""
        return self._set_addresses("Bcc", addresses)

    def get_bcc(self) -> list[Address]:
        """Return the hidden recipients."""
        return get_addresses(self.get_headers(), "Bcc")

    def priority(self, priority: int) -> Self:
        """Set X-Priority, from 1 (highest) to 5 (lowest); a value outside is brought inside."""
        self.get_headers().set_header_body("text", "X-Priority", priority_value(priority))
        return self

    def get_priority(self) -> int:
        """Return the priority X-Priority starts with, normal (3) when it starts with none."""
        return read_priority(self.get_headers())

    def text(self, body: Body | None, charset: str = "utf-8") -> Self:
        """Set the text body, in ``charset``; ``None`` takes it away.

        Raises:
            TypeError: ``body`` is not a string, bytes, a binary file or ``None``.
        """
        self._text = _check_body(body)
        self._text_charset = charset
        self._cached_body = None
        return self

    def get_text_body(self) -> Body | None:
        """Return the text body as given, ``None`` unless set."""
        return self._text

    def get_text_charset(self) -> str | None:
        """Return the charset of the text body, ``None`` unless set."""
        return self._text_charset

    def html(self, body: Body | None, charset: str = "utf-8") -> Self:
        """Set the HTML body, in ``charset``; ``None`` takes it away.

        Raises:
            TypeError: ``body`` is not a string, bytes, a binary file or ``None``.
        """
        self._html = _check_body(body)
        self._html_charset = charset
        self._cached_body = None
        return self

    def get_html_body(self) -> Body | None:
        """Return the HTML body as given, ``None`` unless set."""
        return self._html

    def get_html_charset(self) -> str | None:
        """Return the charset of the HTML body, ``None`` unless set."""
        return self._html_charset

    def attach(self, body: Body, name: str | None = None, content_type: str | None = None) -> Self:
        """Attach content, ``application/octet-stream`` unless ``content_type`` says otherwise."""
        return self.add_part(DataPart(body, name, content_type))

    def attach_from_path(
        self, path: str | PathLike[str], name: str | None = None, content_type: str | None = None
    ) -> Self:
        """Attach a file, read when the email is rendered; its extension gives its type."""
        return self.add_part(DataPart(File(path), name, content_type))

    def embed(self, body: Body, name: str | None = None, content_type: str | None = None) -> Self:
        """Attach content shown inside the body: ``cid:<name>`` in the HTML refers to it."""
        return self.add_part(DataPart(body, name, content_type).as_inline())

    def embed_from_path(
        self, path: str | PathLike[str], name: str | None = None, content_type: str | None = None
    ) -> Self:
        """Attach a file shown inside the body: ``cid:<name>`` in the HTML refers to it."""
        return self.add_part(DataPart(File(path), name, content_type).as_inline())

    def add_part(self, part: DataPart) -> Self:
        """Attach ``part``, after the attachments already there."""
        self._attachments.append(part)
        self._cached_body = None
        return self

    def get_attachments(self) -> list[DataPart]:
        """Return the attachments, in order; changing the list leaves the email as it is."""
        return list(self._attachments)

    @override
    def get_body(self) -> AbstractPart:
        """Return the body set, else the one put together from the text, HTML and attachments.

        Raises:
            LogicError: There is no body set, no text, no HTML and no attachment.
            InvalidArgumentError: The HTML body is bytes in a charset Python does not know.
        """
        body = super().get_body()
        if body is not None:
            return body
        if self._cached_body is None:
            self._cached_body = assemble_body(self)
        return self._cached_body

    @override
    def ensure_validity(self) -> None:
        """Check the email has a body, is not a draft, and names a recipient and an author.

        Raises:
            LogicError: One of those is missing, or X-Unsent marks the email as a draft.
        """
        self._ensure_body_valid()
        if self.get_headers().get_header_body("X-Unsent") == "1":
            raise LogicError('Cannot send messages marked as "draft".')
        super().ensure_validity()

    def _ensure_body_valid(self) -> None:
        """Refuse an email with nothing to send; a subclass with a body of its own overrides it.

        Raises:
            LogicError: There is no body set, no text, no HTML and no attachment.
        """
        if (
            self._text is None
            and self._html is None
            and not self._attachments
            and super().get_body() is None
        ):
            raise LogicError(NO_BODY)

    def _add_addresses(self, name: str, addresses: Iterable[Address | str]) -> Self:
        add_addresses(self.get_headers(), name, addresses)
        return self

    def _set_addresses(self, name: str, addresses: Iterable[Address | str]) -> Self:
        set_addresses(self.get_headers(), name, addresses)
        return self


def _check_body(body: Body | None) -> Body | None:
    if body is None or isinstance(body, str | bytes) or hasattr(body, "read"):
        return body
    raise TypeError(
        f'The body must be a string, bytes, a binary file or None (got "{type(body).__name__}").'
    )
