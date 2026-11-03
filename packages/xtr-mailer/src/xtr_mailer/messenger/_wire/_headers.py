"""Headers as a queued email carries them: each of the class it was, its name checked first.

A header travels as its kind, name, charset, language and what its class holds. Its name is
checked before any header class sees it — printable ASCII, at most 256 characters — so a name
read from the queue never reaches a class whose refusal would repeat it. What it holds is
bounded, and the headers of a part together, before they are built: see ``_header_limits``.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Final, cast

from xtr_mime import (
    DateHeader,
    FoldedHeader,
    Headers,
    IdentificationHeader,
    MailboxHeader,
    MailboxListHeader,
    ParameterizedHeader,
    PathHeader,
    UnstructuredHeader,
)

from xtr_mailer.exception import InvalidArgumentError
from xtr_mailer.header import MetadataHeader, TagHeader, TrackingHeader

from ._addresses import read_address, read_entry, write_address, write_entry
from ._header_limits import (
    BLOCK_LENGTH,
    VALUE_LENGTH,
    carried,
    header_value,
    listed,
    parameters,
)
from ._json import (
    JsonObject,
    built,
    fields,
    items,
    kind_of,
    number,
    optional_text,
    refuse,
    text,
)

if TYPE_CHECKING:
    from xtr_mime import HeaderInterface

__all__ = ["read_headers", "write_headers"]

_NAME: Final = re.compile(r"[!-~]{1,256}")
_SHORT: Final = 64
_COMMON: Final = ("$type", "name", "charset", "language")
# What each kind holds beside the fields every header has.
_KINDS: Final = {
    "text": ("value",),
    "parameterized": ("value", "parameters"),
    "mailbox": ("address",),
    "mailbox_list": ("entries",),
    "date": ("value",),
    "id": ("ids",),
    "path": ("address",),
    "folded": ("field",),
    "tag": ("value",),
    "metadata": ("key", "value"),
    "tracking": ("opens", "clicks", "value"),
}
# The classes carried; a subclass of one is not, as it would come back as its base.
_CARRIED: Final = frozenset(
    {
        DateHeader,
        FoldedHeader,
        IdentificationHeader,
        MailboxHeader,
        MailboxListHeader,
        MetadataHeader,
        ParameterizedHeader,
        PathHeader,
        TagHeader,
        TrackingHeader,
        UnstructuredHeader,
    }
)


def write_headers(headers: Headers) -> JsonObject:
    """Write every header in order, and the line length they are folded at.

    Raises:
        InvalidArgumentError: A header is of a class the queue does not carry.
    """
    return {
        "line_length": headers.get_max_line_length(),
        "fields": [_write(header) for header in headers.all()],
    }


def read_headers(data: object, path: str, headers: Headers | None = None) -> Headers:
    """Read headers written by :func:`write_headers`, held to the rules :class:`Headers` sets.

    They are added to ``headers`` when given — those a part holds from the start.

    Raises:
        InvalidArgumentError: The data is not such headers.
    """
    found = fields(data, path, ("line_length", "fields"))
    line_length = number(found["line_length"], f"{path}.line_length", 1, 998)
    read = Headers() if headers is None else headers
    spent = 0
    for index, entry in enumerate(items(found["fields"], f"{path}.fields")):
        where = f"{path}.fields[{index}]"
        header = _read(entry, where)
        spent += carried(header)
        if spent > BLOCK_LENGTH:
            refuse(path, f"holds more than {BLOCK_LENGTH} characters of header text")
        _ = built(where, "a header these headers may hold", lambda h=header: read.add(h))
    read.set_max_line_length(line_length)
    return read


def _write(header: HeaderInterface) -> JsonObject:
    if type(header) not in _CARRIED:
        raise InvalidArgumentError(
            f'A header of class "{type(header).__qualname__}" cannot be queued.'
        )
    kind, held = _held(header)
    common = {"name": header.get_name(), "charset": header.get_charset()}
    return {"$type": kind, **common, "language": header.get_language(), **held}


def _held(header: HeaderInterface) -> tuple[str, JsonObject]:
    # The class is one carried: a subclass is matched before its base.
    match header:
        case UnstructuredHeader():
            return _held_text(header)
        case MailboxHeader():
            return "mailbox", {"address": write_address(header.get_address())}
        case MailboxListHeader():
            return "mailbox_list", {"entries": list(map(write_entry, header.get_address_list()))}
        case DateHeader():
            return "date", {"value": header.get_date_time().isoformat()}
        case IdentificationHeader():
            return "id", {"ids": header.get_ids()}
        case _:
            return "path", {"address": write_address(cast("PathHeader", header).get_address())}


def _held_text(header: UnstructuredHeader) -> tuple[str, JsonObject]:
    match header:
        case TagHeader():
            return "tag", {"value": header.get_value()}
        case MetadataHeader():
            return "metadata", {"key": header.get_key(), "value": header.get_value()}
        case TrackingHeader():
            flags = {"opens": header.get_opens(), "clicks": header.get_clicks()}
            return "tracking", {**flags, "value": header.get_value()}
        case FoldedHeader():
            return "folded", {"field": header.to_string()}
        case ParameterizedHeader():
            pairs = [[key, value] for key, value in header.get_parameters().items()]
            return "parameterized", {"value": header.get_value(), "parameters": pairs}
        case _:
            return "text", {"value": header.get_value()}


def _read(data: object, path: str) -> HeaderInterface:
    kind = kind_of(data)
    if type(kind) is not str or kind not in _KINDS:
        refuse(path, "is not a header of a kind the queue carries")
    found = fields(data, path, (*_COMMON, *_KINDS[kind]))
    name = found["name"]
    if type(name) is not str or not _NAME.fullmatch(name):
        refuse(f"{path}.name", "is not a header name: 1 to 256 printable ASCII characters")
    charset = text(found["charset"], f"{path}.charset", _SHORT)
    language = optional_text(found["language"], f"{path}.language", _SHORT)
    header = _built(kind, name, found, path)
    if header.get_name() != name:
        refuse(f"{path}.name", "is not the name a header of its kind has")
    header.set_charset(charset)
    if language is not None:
        header.set_language(language)
    return header


def _built(kind: str, name: str, found: JsonObject, path: str) -> HeaderInterface:
    match kind:
        case "mailbox" | "path":
            address = read_address(found["address"], f"{path}.address")
            header = MailboxHeader if kind == "mailbox" else PathHeader
            return built(path, "a header", lambda: header(name, address))
        case "mailbox_list":
            listing = listed(found["entries"], f"{path}.entries")
            entries = [read_entry(item, f"{path}.entries[{i}]") for i, item in enumerate(listing)]
            return built(path, "a header", lambda: MailboxListHeader(name, entries))
        case "id":
            listing = listed(found["ids"], f"{path}.ids")
            ids = [header_value(item, f"{path}.ids[{i}]") for i, item in enumerate(listing)]
            return built(path, "a header", lambda: IdentificationHeader(name, ids))
        case "parameterized":
            value = header_value(found["value"], f"{path}.value")
            held = dict(parameters(found["parameters"], f"{path}.parameters"))
            return built(path, "a header", lambda: ParameterizedHeader(name, value, held))
        case "folded":
            # The field holds its folds; its class refuses any other line break.
            field = text(found["field"], f"{path}.field", VALUE_LENGTH)
            return built(path, "a header", lambda: FoldedHeader(field))
        case _:
            return _built_text(kind, name, found, path)


def _built_text(kind: str, name: str, found: JsonObject, path: str) -> HeaderInterface:
    value = header_value(found["value"], f"{path}.value")
    match kind:
        case "date":
            return built(path, "a header", lambda: DateHeader(name, datetime.fromisoformat(value)))
        case "tag":
            return built(path, "a header", lambda: TagHeader(value))
        case "metadata":
            key = header_value(found["key"], f"{path}.key", 256)
            return built(path, "a header", lambda: MetadataHeader(key, value))
        case "tracking":
            opens = _flag(found["opens"], f"{path}.opens")
            tracking = TrackingHeader(opens, _flag(found["clicks"], f"{path}.clicks"))
            tracking.set_value(value)
            return tracking
        case _:
            return built(path, "a header", lambda: UnstructuredHeader(name, value))


def _flag(data: object, path: str) -> bool | None:
    if data is not None and type(data) is not bool:
        refuse(path, "is not true, false or null")
    return data
