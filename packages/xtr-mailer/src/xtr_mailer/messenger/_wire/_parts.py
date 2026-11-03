"""The parts holding a body — text, data, S/MIME — as a queued email carries them.

A body travels as its content: a file is read and a stream drained when the email is queued.
A path is never written, nor read back: one read from the queue would let a forged message
attach any file the worker can read.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, TypeVar, cast

from xtr_mime import DataPart, ParameterizedHeader, SMimePart, TextPart

from ._header_limits import parameters
from ._headers import read_headers, write_headers
from ._json import (
    JsonObject,
    built,
    content,
    decoded,
    encoded,
    fields,
    kind_of,
    optional_text,
    refuse,
    text,
    written_content,
)

if TYPE_CHECKING:
    from xtr_mime import AbstractPart

__all__ = ["read_leaf", "write_leaf"]

_P = TypeVar("_P", bound=TextPart)

_SHORT: Final = 256
_TEXT: Final = ("headers", "body", "charset", "subtype", "encoding", "disposition", "name")
_DATA: Final = ("headers", "body", "filename", "content_type", "encoding", "disposition")
_DATA_MORE: Final = ("name", "content_id")
_SMIME: Final = ("headers", "body", "media_type", "media_subtype", "parameters")


def write_leaf(part: AbstractPart) -> JsonObject | None:
    """Write a text, data or S/MIME part; ``None`` for a part of any other class.

    Raises:
        InvalidArgumentError: The body is a file that cannot be read.
    """
    kind = type(part)
    if kind is SMimePart:
        content_type = part.get_prepared_headers().get("Content-Type")
        parameters = (
            content_type.get_parameters() if isinstance(content_type, ParameterizedHeader) else {}
        )
        return {
            "$type": "smime",
            "headers": write_headers(part.get_headers()),
            "body": encoded(b"".join(part.body_to_iterable())),
            "media_type": part.get_media_type(),
            "media_subtype": part.get_media_subtype(),
            "parameters": [[k, v] for k, v in parameters.items() if v is not None],
        }
    if kind is not TextPart and kind is not DataPart:
        return None
    leaf = cast("TextPart", part)
    prepared = leaf.get_prepared_headers()
    written: JsonObject = {
        "headers": write_headers(leaf.get_headers()),
        "body": written_content(leaf.get_body()),
        "encoding": prepared.get_header_body("Content-Transfer-Encoding"),
        "disposition": leaf.get_disposition(),
        "name": leaf.get_name(),
    }
    if isinstance(leaf, DataPart):
        content_id = leaf.get_content_id() if leaf.has_content_id() else None
        data = {"filename": leaf.get_filename(), "content_type": leaf.get_content_type()}
        return {"$type": "data", **written, **data, "content_id": content_id}
    charset = prepared.get_header_parameter("Content-Type", "charset") or None
    return {"$type": "text", **written, "charset": charset, "subtype": leaf.get_media_subtype()}


def read_leaf(data: object, path: str) -> AbstractPart:
    """Read a part written by :func:`write_leaf`.

    Raises:
        InvalidArgumentError: It is not one.
    """
    match kind_of(data):
        case "text":
            found = fields(data, path, ("$type", *_TEXT))
            part = _text(found, path)
        case "data":
            found = fields(data, path, ("$type", *_DATA, *_DATA_MORE))
            part = _data(found, path)
        case "smime":
            found = fields(data, path, ("$type", *_SMIME))
            part = _smime(found, path)
        case _:
            refuse(path, "is not a part of a class the queue carries")
    _ = read_headers(found["headers"], f"{path}.headers", part.get_headers())
    return part


def _text(found: JsonObject, path: str) -> TextPart:
    body = content(found["body"], f"{path}.body")
    charset = optional_text(found["charset"], f"{path}.charset", _SHORT)
    subtype = text(found["subtype"], f"{path}.subtype", _SHORT)
    encoding = text(found["encoding"], f"{path}.encoding", _SHORT)
    part = built(path, "a text part", lambda: TextPart(body, charset, subtype, encoding))
    return _shown(part, found, path)


def _data(found: JsonObject, path: str) -> DataPart:
    body = content(found["body"], f"{path}.body")
    filename = optional_text(found["filename"], f"{path}.filename", _SHORT)
    content_type = text(found["content_type"], f"{path}.content_type", _SHORT)
    encoding = text(found["encoding"], f"{path}.encoding", _SHORT)
    content_id = optional_text(found["content_id"], f"{path}.content_id", _SHORT)
    part = built(path, "a data part", lambda: DataPart(body, filename, content_type, encoding))
    if content_id is not None:
        _ = built(f"{path}.content_id", "a content id", lambda: part.set_content_id(content_id))
    return _shown(part, found, path)


def _shown(part: _P, found: JsonObject, path: str) -> _P:
    disposition = optional_text(found["disposition"], f"{path}.disposition", _SHORT)
    name = optional_text(found["name"], f"{path}.name", _SHORT)
    if disposition is not None:
        _ = part.set_disposition(disposition)
    if name is not None:
        _ = part.set_name(name)
    return part


def _smime(found: JsonObject, path: str) -> SMimePart:
    body = decoded(found["body"], f"{path}.body")
    media_type = text(found["media_type"], f"{path}.media_type", _SHORT)
    media_subtype = text(found["media_subtype"], f"{path}.media_subtype", _SHORT)
    held = {
        name: value
        for name, value in parameters(found["parameters"], f"{path}.parameters")
        if value is not None
    }
    return built(path, "an S/MIME part", lambda: SMimePart(body, media_type, media_subtype, held))
