"""Reading the plain data a queued email travels as, one checked value at a time.

What a broker hands over is untrusted: each value is checked for the type and size it must
have, and a refusal says where, by the field names and indexes of this format, and why, in
words of its own — never what the data held, which could be anything, megabytes of it.
"""

from __future__ import annotations

import base64
import binascii
from typing import TYPE_CHECKING, Final, NoReturn, TypeAlias, TypeVar, cast

from xtr_mime import MimeError

from xtr_mailer.exception import InvalidArgumentError, MailerError

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "JsonObject",
    "built",
    "content",
    "decoded",
    "encoded",
    "fields",
    "holds",
    "items",
    "kind_of",
    "number",
    "optional_text",
    "pairs",
    "refuse",
    "text",
    "written_content",
]

JsonObject: TypeAlias = dict[str, object]
"""An object of the format, as JSON reads it: text keys."""

_T = TypeVar("_T")

# What the classes the data is handed to raise on a value they refuse; their words may
# repeat the value, so they are not passed on.
_REFUSED: Final = (MimeError, MailerError, ValueError, TypeError)


def refuse(path: str, reason: str) -> NoReturn:
    """Refuse the data at ``path``.

    Raises:
        InvalidArgumentError: Always.
    """
    raise InvalidArgumentError(f"The queued email cannot be read: {path} {reason}.")


def fields(
    data: object, path: str, required: tuple[str, ...], optional: tuple[str, ...] = ()
) -> JsonObject:
    """Give the fields of an object holding every ``required`` one and no other but ``optional``.

    Raises:
        InvalidArgumentError: ``data`` is no such object.
    """
    if type(data) is not dict:
        refuse(path, "is not an object")
    found = cast("JsonObject", data)
    if not set(required) <= found.keys() <= {*required, *optional}:
        refuse(path, "does not hold the fields it must")
    return found


def kind_of(data: object) -> object:
    """Give the ``$type`` an object names its kind under; ``None`` for anything else."""
    return cast("JsonObject", data).get("$type") if type(data) is dict else None


def holds(data: object, name: str) -> bool:
    """Tell whether ``data`` is an object holding a field ``name``."""
    return type(data) is dict and name in cast("JsonObject", data)


def text(data: object, path: str, limit: int | None = None) -> str:
    """Give ``data`` as text of at most ``limit`` characters.

    Raises:
        InvalidArgumentError: It is not text, or is longer.
    """
    if type(data) is not str:
        refuse(path, "is not text")
    if limit is not None and len(data) > limit:
        refuse(path, f"is longer than {limit} characters")
    return data


def optional_text(data: object, path: str, limit: int | None = None) -> str | None:
    """Give ``data`` as text, or ``None`` for null.

    Raises:
        InvalidArgumentError: It is neither.
    """
    return None if data is None else text(data, path, limit)


def items(data: object, path: str) -> list[object]:
    """Give the items of a list.

    Raises:
        InvalidArgumentError: ``data`` is not one.
    """
    if type(data) is not list:
        refuse(path, "is not a list")
    return cast("list[object]", data)


def number(data: object, path: str, low: int, high: int) -> int:
    """Give ``data`` as a whole number from ``low`` to ``high``.

    Raises:
        InvalidArgumentError: It is not one, or is outside.
    """
    if type(data) is not int or not low <= data <= high:
        refuse(path, f"is not a whole number from {low} to {high}")
    return data


def pairs(data: object, path: str) -> list[tuple[str, str | None]]:
    """Give the name and value of each parameter in a list of them; a value may be null.

    Raises:
        InvalidArgumentError: ``data`` is no list of names and values.
    """
    found: list[tuple[str, str | None]] = []
    for index, pair in enumerate(items(data, path)):
        where = f"{path}[{index}]"
        listed = items(pair, where)
        if len(listed) != 2:  # noqa: PLR2004 -- a name and its value.
            refuse(where, "is not a parameter: a name and its value")
        found.append((text(listed[0], f"{where}[0]", 64), optional_text(listed[1], f"{where}[1]")))
    return found


def encoded(data: bytes) -> str:
    """Write bytes as base64 text."""
    return base64.b64encode(data).decode("ascii")


def decoded(data: object, path: str) -> bytes:
    """Give the bytes base64 text holds.

    Raises:
        InvalidArgumentError: ``data`` is not base64 text.
    """
    if type(data) is str:
        try:
            return base64.b64decode(data, validate=True)
        except (binascii.Error, ValueError):
            pass
    refuse(path, "is not base64")


def written_content(body: str | bytes) -> JsonObject:
    """Write a body as it was given: text as text, bytes as base64."""
    return {"text": body} if isinstance(body, str) else {"bytes": encoded(body)}


def content(data: object, path: str) -> str | bytes:
    """Give a body written by :func:`written_content` back as text or bytes.

    Raises:
        InvalidArgumentError: ``data`` is neither.
    """
    found = fields(data, path, (), ("text", "bytes"))
    if len(found) != 1:
        refuse(path, "is not a body: text or bytes")
    if "text" in found:
        return text(found["text"], f"{path}.text")
    return decoded(found["bytes"], f"{path}.bytes")


def built(path: str, what: str, build: Callable[[], _T]) -> _T:
    """Give what ``build`` builds, refused at ``path`` as not ``what`` when its class refuses it.

    The class's error is dropped, not chained: its words may repeat the data.

    Raises:
        InvalidArgumentError: The class refused it.
    """
    try:
        return build()
    except _REFUSED:
        pass
    refuse(path, f"is not {what}")
