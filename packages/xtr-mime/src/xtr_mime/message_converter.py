"""Turns a message with a simple body back into an email."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .crypto.signed_body import SignedBody
from .email import Email
from .exception import MimeRuntimeError
from .part import AlternativePart, DataPart, MixedPart, RelatedPart, SMimePart, TextPart

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .message import Message
    from .part import AbstractPart

__all__ = ["MessageConverter"]


@final
class MessageConverter:
    """Reads an email's text, HTML and attachments back out of a message's body tree.

    A transport that hands a provider's API fields — not MIME — needs them. Only the trees an
    email builds are understood: a text or HTML part, both in ``alternative``, inside
    ``related`` with inline parts, inside ``mixed`` with attachments.

    A message signed with DKIM is read from the part its signature was made over, so the email
    carries the same text, HTML and attachments. A body signed or encrypted with S/MIME is
    refused: its fields cannot be handed over apart from the signature or the encryption.
    """

    @staticmethod
    def to_email(message: Message) -> Email:
        """Return ``message`` if it is an email, else an email with its headers and body.

        Raises:
            MimeRuntimeError: The body is not a tree an email builds, or is signed or
                encrypted with S/MIME.
        """
        if isinstance(message, Email):
            return message
        body = message.get_body()
        if isinstance(body, SignedBody):
            body = body.get_signed_part()
        match body:
            case SMimePart():
                raise _refused(
                    message,
                    "is signed or encrypted with S/MIME: only the whole message can be sent",
                )
            case MixedPart():
                return _from_parts(message, body.get_parts(), related=True)
            case _:
                return _from_main_part(message, body, related=True)


def _from_main_part(message: Message, part: AbstractPart | None, *, related: bool) -> Email:
    match part:
        case RelatedPart() if related:
            return _from_parts(message, part.get_parts(), related=False)
        case AlternativePart():
            return _from_alternative_part(message, part)
        case TextPart():
            return _from_text_part(message, part)
        case _:
            raise _too_complex(message)


def _from_parts(message: Message, parts: Sequence[AbstractPart], *, related: bool) -> Email:
    """Read the email from the first part, then add every other part as an attachment."""
    match parts:
        case [first, *rest]:
            return _add_parts(message, _from_main_part(message, first, related=related), rest)
        case _:
            raise _too_complex(message)


def _from_text_part(message: Message, part: TextPart) -> Email:
    # The clock stays inside xtr-mime: the email the message becomes is its one other reader.
    clock = message._clock  # noqa: SLF001  # pyright: ignore[reportPrivateUsage] -- see above.
    email = Email(message.get_headers(), clock=clock)
    match part.get_media_type(), part.get_media_subtype():
        case "text", "plain":
            return email.text(part.get_body(), _charset(part))
        case "text", "html":
            return email.html(part.get_body(), _charset(part))
        case _:
            raise _too_complex(message)


def _from_alternative_part(message: Message, part: AlternativePart) -> Email:
    match part.get_parts():
        case [TextPart() as text, TextPart() as html] if (
            text.get_media_type(),
            text.get_media_subtype(),
        ) == ("text", "plain") and (html.get_media_type(), html.get_media_subtype()) == (
            "text",
            "html",
        ):
            email = _from_text_part(message, text)
            return email.html(html.get_body(), _charset(html))
        case _:
            raise _too_complex(message)


def _add_parts(message: Message, email: Email, parts: Sequence[AbstractPart]) -> Email:
    for part in parts:
        if not isinstance(part, DataPart):
            raise _too_complex(message)
        _ = email.add_part(part)
    return email


def _charset(part: TextPart) -> str:
    return part.get_prepared_headers().get_header_parameter("Content-Type", "charset") or "utf-8"


def _too_complex(message: Message) -> MimeRuntimeError:
    return _refused(message, "is too complex")


def _refused(message: Message, reason: str) -> MimeRuntimeError:
    cls = type(message)
    module = "xtr_mime" if cls.__module__.startswith("xtr_mime.") else cls.__module__
    return MimeRuntimeError(
        f'Unable to create an Email from an instance of "{module}.{cls.__qualname__}" as the '
        f"body {reason}."
    )
