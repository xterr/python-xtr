"""Messages and their part trees as a queued email carries them, each of the class it was.

A raw message travels as its bytes. A message or an email travels as its headers and body —
for an email, the text, HTML and attachments its body is put together from, and the template
of an email a provider renders — so the listeners of the worker change it as they would have
here. A body frozen at signing travels as its bytes, and renders them again exactly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast

from xtr_mime import (
    AbstractMultipartPart,
    AlternativePart,
    DigestPart,
    DraftEmail,
    Email,
    Message,
    MessagePart,
    MixedPart,
    RawMessage,
    RelatedPart,
    SignedBody,
)

from xtr_mailer.exception import InvalidArgumentError
from xtr_mailer.remote_template_email import RemoteTemplateEmail

from ._email_fields import EMAIL_FIELDS, TEMPLATE_FIELD, read_email_fields, write_email_fields
from ._headers import read_headers, write_headers
from ._json import JsonObject, built, decoded, encoded, fields, items, kind_of, refuse
from ._parts import read_leaf, write_leaf
from ._render_budget import PART_COUNT

if TYPE_CHECKING:
    from xtr_mime import AbstractPart

__all__ = ["read_message", "write_message"]

# Deeper than any mail a client writes; the bound keeps reading a forged tree cheap.
_DEPTH: Final = 32
_MESSAGES: Final[dict[type[Message], str]] = {
    Message: "message",
    Email: "email",
    DraftEmail: "draft_email",
    RemoteTemplateEmail: "remote_template_email",
}
_MESSAGE_CLASSES: Final = {name: kind for kind, name in _MESSAGES.items()}
_MULTIPARTS: Final[dict[type[AbstractMultipartPart], str]] = {
    AlternativePart: "alternative",
    MixedPart: "mixed",
    RelatedPart: "related",
    DigestPart: "digest",
}
_MULTIPART_CLASSES: Final = {name: kind for kind, name in _MULTIPARTS.items()}


def write_message(message: RawMessage, depth: int = 0) -> JsonObject:
    """Write ``message`` as the class it is.

    Raises:
        InvalidArgumentError: It, or a part or header in it, is of a class the queue does not
            carry, or its parts are nested deeper than 32.
        LogicError: A raw message is a generator left half read.
    """
    kind = type(message)
    if kind is RawMessage:
        return {"$type": "raw", "body": encoded(b"".join(message.to_iterable()))}
    name = _MESSAGES.get(cast("type[Message]", kind))
    if name is None:
        raise InvalidArgumentError(f'An email of class "{kind.__qualname__}" cannot be queued.')
    built_message = cast("Message", message)
    body = Message.get_body(built_message)
    written: JsonObject = {
        "$type": name,
        "headers": write_headers(built_message.get_headers()),
        "body": None if body is None else _write_part(body, depth + 1),
    }
    if isinstance(built_message, Email):
        written |= write_email_fields(built_message, lambda part: _write_part(part, depth + 1))
    return written


def read_message(data: object, path: str, depth: int = 0) -> RawMessage:
    """Read a message written by :func:`write_message`.

    Raises:
        InvalidArgumentError: It is not one, or its parts are nested deeper than 32.
    """
    kind = kind_of(data)
    if kind == "raw":
        found = fields(data, path, ("$type", "body"))
        return RawMessage(decoded(found["body"], f"{path}.body"))
    message_class = _MESSAGE_CLASSES.get(kind) if type(kind) is str else None
    if message_class is None:
        refuse(path, "is not a message of a class the queue carries")
    required = ("$type", "headers", "body")
    if issubclass(message_class, Email):
        required += EMAIL_FIELDS
    if message_class is RemoteTemplateEmail:
        required += (TEMPLATE_FIELD,)
    found = fields(data, path, required)
    message = message_class()
    _ = message.set_headers(read_headers(found["headers"], f"{path}.headers"))
    if found["body"] is not None:
        _ = message.set_body(_read_part(found["body"], f"{path}.body", depth + 1))
    if isinstance(message, Email):
        read_email_fields(message, found, path, lambda d, p: _read_part(d, p, depth + 1))
    return message


def _write_part(part: AbstractPart, depth: int) -> JsonObject:
    if depth > _DEPTH:
        raise InvalidArgumentError(
            f"An email whose parts are nested deeper than {_DEPTH} cannot be queued."
        )
    leaf = write_leaf(part)
    if leaf is not None:
        return leaf
    match part:
        case AbstractMultipartPart() if type(part) in _MULTIPARTS:
            written = [_write_part(child, depth + 1) for child in part.get_parts()]
            name = _MULTIPARTS[type(part)]
            return {"$type": name, "headers": write_headers(part.get_headers()), "parts": written}
        case MessagePart() if type(part) is MessagePart:
            inner = part.get_message()
            if not isinstance(inner, RawMessage):
                raise InvalidArgumentError(
                    "An attached message that is no message cannot be queued."
                )
            headers = write_headers(part.get_headers())
            return {"$type": "attached", "headers": headers, "message": write_message(inner, depth)}
        case SignedBody():
            body = encoded(b"".join(part.body_to_iterable()))
            signed = _write_part(part.get_signed_part(), depth + 1)
            prepared = write_headers(part.get_prepared_headers())
            return {"$type": "signed", "part": signed, "headers": prepared, "body": body}
        case _:
            raise InvalidArgumentError(
                f'A part of class "{type(part).__qualname__}" cannot be queued.'
            )


def _read_part(data: object, path: str, depth: int) -> AbstractPart:
    if depth > _DEPTH:
        refuse(path, f"is nested deeper than {_DEPTH} parts")
    kind = kind_of(data)
    if kind == "attached":
        found = fields(data, path, ("$type", "headers", "message"))
        message = read_message(found["message"], f"{path}.message", depth)
        part = MessagePart(message)
        return _with_headers(part, found, path)
    if kind == "signed":
        found = fields(data, path, ("$type", "part", "headers", "body"))
        signed = _read_part(found["part"], f"{path}.part", depth + 1)
        prepared = read_headers(found["headers"], f"{path}.headers")
        body = decoded(found["body"], f"{path}.body")
        return SignedBody.from_frozen(signed, prepared, body)
    multipart = _MULTIPART_CLASSES.get(kind) if type(kind) is str else None
    if multipart is None:
        return read_leaf(data, path)
    found = fields(data, path, ("$type", "headers", "parts"))
    listed = items(found["parts"], f"{path}.parts")
    if len(listed) > PART_COUNT:
        refuse(f"{path}.parts", f"holds more than {PART_COUNT} parts")
    parts = [_read_part(item, f"{path}.parts[{i}]", depth + 1) for i, item in enumerate(listed)]
    part = built(path, "a multipart", lambda: _multipart(multipart, parts))
    return _with_headers(part, found, path)


def _multipart(kind: type[AbstractMultipartPart], parts: list[AbstractPart]) -> AbstractPart:
    if kind is DigestPart:
        if not all(isinstance(part, MessagePart) for part in parts):
            raise InvalidArgumentError("A digest holds attached messages only.")
        return DigestPart(*cast("list[MessagePart]", parts))
    if kind is RelatedPart:
        if len(parts) < 2:  # noqa: PLR2004 -- the main part and one it shows.
            raise InvalidArgumentError("A related part holds two parts at least.")
        return RelatedPart(*parts)
    return kind(*parts)


def _with_headers(part: AbstractPart, found: JsonObject, path: str) -> AbstractPart:
    _ = read_headers(found["headers"], f"{path}.headers", part.get_headers())
    return part
