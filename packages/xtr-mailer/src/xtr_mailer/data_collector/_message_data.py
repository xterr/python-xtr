"""The plain data the profiler panel shows of one recorded email."""

from __future__ import annotations

from typing import TYPE_CHECKING, BinaryIO, Final

from xtr_mime import Email, Message
from xtr_mime.exception import MimeError

from xtr_mailer.exception import TransportError

from ._masking import masked_header

if TYPE_CHECKING:
    from xtr_mime import Address
    from xtr_mime.header import HeaderInterface, Headers
    from xtr_mime.part import DataPart

    from xtr_mailer.sent_message import SentMessage

    from ._mail_record import MailRecord

__all__ = ["message_data"]

_TEXT_LIMIT: Final = 10_000
_HTML_LIMIT: Final = 50_000
# A character takes at most four bytes in UTF-8: decoding this many is enough for the limit.
_BYTES_PER_CHARACTER: Final = 4


def message_data(record: MailRecord) -> dict[str, object]:
    """Return what the panel shows of ``record``: how it was sent and, for an email, what it says.

    Read once the request is over, so nothing here runs while the email is being sent. A
    message that is not an email — raw bytes, or one signed as a whole — has no fields to
    read, so it is described by its transport, its status and its size alone.
    """
    event = record.event
    sent = record.sent
    error = record.error
    data: dict[str, object] = {
        "transport": event.get_transport(),
        "queued": event.is_queued(),
        "status": record.status(),
        "subject": None,
        "from": [],
        "to": [],
        "cc": [],
        "bcc": [],
        "reply_to": [],
        "headers": {},
        "text": None,
        "html": None,
        "attachments": [],
        "message_id": (sent.get_message_id() or None) if sent is not None else None,
        "debug": _debug(sent, error),
        "error": None if error is None else (str(error) or type(error).__name__),
        "size": _size(record),
    }
    email = next(
        (each for each in (event.get_message(), record.original) if isinstance(each, Email)), None
    )
    if email is not None:
        data.update(_email_data(email))
    return data


def _email_data(email: Email) -> dict[str, object]:
    return {
        "subject": email.get_subject(),
        "from": _addresses(email.get_from()),
        "to": _addresses(email.get_to()),
        "cc": _addresses(email.get_cc()),
        "bcc": _addresses(email.get_bcc()),
        "reply_to": _addresses(email.get_reply_to()),
        "headers": _headers(email.get_headers()),
        "text": _body(email.get_text_body(), email.get_text_charset(), _TEXT_LIMIT),
        "html": _body(email.get_html_body(), email.get_html_charset(), _HTML_LIMIT),
        "attachments": [_attachment(part) for part in email.get_attachments()],
    }


def _addresses(addresses: list[Address]) -> list[str]:
    """Write each address as a reader sees it, without the engine: it cannot refuse one here."""
    return [
        f"{address.get_name()} <{address.get_address()}>"
        if address.get_name()
        else address.get_address()
        for address in addresses
    ]


def _headers(headers: Headers) -> dict[str, str]:
    """Return each header by name, a repeated one on several lines, credentials masked."""
    kept: dict[str, str] = {}
    for header in headers.all():
        name = header.get_name()
        value = masked_header(name, _header_value(header))
        kept[name] = f"{kept[name]}\n{value}" if name in kept else value
    return kept


def _header_value(header: HeaderInterface) -> str:
    """Return the value as it is written, or as given when the engine would refuse it.

    The engine refusing a header is why the send failed, so the panel still shows it.
    """
    try:
        return header.get_body_as_string()
    except MimeError:
        return str(header.get_body())


def _body(body: str | bytes | BinaryIO | None, charset: str | None, limit: int) -> str | None:
    """Return the first ``limit`` characters of a body; a file body is not read.

    A file is read as the email is rendered, possibly once only: reading it here could
    leave nothing for the send.
    """
    match body:
        case None:
            return None
        case str():
            return body[:limit]
        case bytes():
            return _decoded(body[: limit * _BYTES_PER_CHARACTER], charset)[:limit]
        case _:
            return None


def _decoded(content: bytes, charset: str | None) -> str:
    """Decode ``content`` in its charset, or in UTF-8 when Python does not know the charset."""
    try:
        return content.decode(charset or "utf-8", "replace")
    except LookupError:
        return content.decode("utf-8", "replace")


def _attachment(part: DataPart) -> dict[str, object]:
    return {
        "filename": part.get_filename(),
        "content_type": part.get_content_type(),
        "size": _part_size(part),
    }


def _part_size(part: DataPart) -> int | None:
    """Return the size of an attachment, ``None`` when it can no longer be read.

    The attachment is read after the send: its file may have gone, or its stream been closed.
    """
    try:
        body = part.get_body()
    except MimeError, OSError, ValueError:
        return None
    return len(body.encode("utf-8", "replace") if isinstance(body, str) else body)


def _debug(sent: SentMessage | None, error: Exception | None) -> str | None:
    """Return the transcript of the failure, else of the send; neither carries a credential."""
    if isinstance(error, TransportError) and error.debug:
        return error.debug
    if sent is not None and sent.get_debug():
        return sent.get_debug()
    return None


def _size(record: MailRecord) -> int | None:
    """Return the size in bytes of what was sent, or of a raw message that was not.

    A message that was not sent is not rendered for this: rendering is the send's work, and
    it may be what failed. Reading what is left after the send can fail too — a stream read
    to its end and closed — and then the size is unknown.
    """
    sent = record.sent
    message = sent.get_message() if sent is not None else record.event.get_message()
    if sent is None and isinstance(message, Message):
        return None
    try:
        content = b"".join(message.to_iterable())
    except MimeError, OSError, ValueError:
        return None
    return len(content)
