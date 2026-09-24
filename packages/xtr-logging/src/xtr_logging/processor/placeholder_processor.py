"""Fills ``{placeholders}`` in a message from its context."""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Mapping
from dataclasses import replace
from enum import Enum
from typing import TYPE_CHECKING, Final, final

import msgspec
from typing_extensions import override

from xtr_logging.formatter.normalizer import Normalizer

from .processor_interface import ProcessorInterface

if TYPE_CHECKING:
    from xtr_logging.log_record import LogRecord

__all__ = ["PlaceholderProcessor"]

_PLACEHOLDER: Final = re.compile(r"\{([A-Za-z0-9_.]+)\}")


@final
class PlaceholderProcessor(ProcessorInterface):
    """Replaces ``{key}`` in a message with ``context[key]``.

    A caller writes ``logger.info("User {id} signed in", {"id": 7})`` and the
    message becomes ``"User 7 signed in"``. Only placeholders with a matching
    context key are filled; the rest are left as written. A value is rendered
    the way a log reader expects — ``null``, ``true``, an object's own text, a
    nested value as ``array{...}`` — never by failing.

    With ``remove_used_context_fields`` the keys that were substituted are
    dropped from the context, so they are not also printed beside the message.
    """

    __slots__ = ("_normalizer", "_remove_used_context_fields")

    def __init__(
        self,
        date_format: str | None = None,
        *,
        remove_used_context_fields: bool = False,
    ) -> None:
        """Render values, dropping substituted keys when asked.

        Args:
            date_format: A :meth:`~datetime.datetime.strftime` format for
                datetime values; ISO 8601 when omitted.
            remove_used_context_fields: Drop each substituted key from the
                context once it is in the message.
        """
        self._normalizer: Normalizer = Normalizer(date_format)
        self._remove_used_context_fields: bool = remove_used_context_fields

    @override
    def __call__(self, record: LogRecord, /) -> LogRecord:
        """Return ``record`` with its message interpolated from its context."""
        if "{" not in record.message:
            return record
        context = record.context
        used: set[str] = set()

        def substitute(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in context:
                return match.group(0)
            used.add(key)
            return self._render(context[key])

        message = _PLACEHOLDER.sub(substitute, record.message)
        if not (self._remove_used_context_fields and used):
            return replace(record, message=message)
        remaining = {key: value for key, value in context.items() if key not in used}
        return replace(record, message=message, context=remaining)

    def _render(self, value: object) -> str:  # noqa: PLR0911 — one branch per kind of value
        match value:
            case None:
                return "null"
            case Enum():
                return self._render(value.value)  # pyright: ignore[reportAny] — an enum's value is whatever it was declared with
            case bool():
                return "true" if value else "false"
            case str():
                return value
            case dt.datetime():
                return self._normalizer.format_datetime(value)
            case BaseException():
                return f"{_class_name(value)}: {value}"
            case Mapping() | list() | tuple():
                plain = self._normalizer.normalize(value)  # pyright: ignore[reportUnknownArgumentType] — a logged collection holds whatever the caller put in
                return "array" + msgspec.json.encode(plain).decode()
            case int() | float():
                return str(value)
            case _:
                return _describe(value)


def _class_name(value: object) -> str:
    kind = type(value)
    if kind.__module__ == "builtins":
        return kind.__qualname__
    return f"{kind.__module__}.{kind.__qualname__}"


def _describe(value: object) -> str:
    kind = type(value)
    if kind.__str__ is not object.__str__ or kind.__repr__ is not object.__repr__:
        return str(value)
    return f"[object {_class_name(value)}]"
