"""Reducing any logged value to something every output format can hold."""

from __future__ import annotations

import dataclasses
import datetime as dt
import math
import traceback
from collections.abc import Mapping
from enum import Enum
from typing import Final, TypeAlias

__all__ = ["Normalized", "Normalizer"]

Normalized: TypeAlias = "bool | int | float | str | list[Normalized] | dict[str, Normalized] | None"
"""A value JSON can hold: what :meth:`Normalizer.normalize` returns."""

_DEFAULT_MAX_DEPTH: Final = 9
_DEFAULT_MAX_ITEMS: Final = 1000


class Normalizer:
    """Turns anything a caller logged into plain data.

    Context is data from the caller, never a reason to fail: a value that
    cannot be serialised is described instead. Nesting deeper than
    ``max_depth``, or a collection longer than ``max_items``, is cut short
    with a note saying so, so one enormous value cannot stall a handler.

    Subclass to render a kind of value differently; formatters override
    :meth:`_normalize_exception` to print exceptions their own way.
    """

    def __init__(
        self,
        date_format: str | None = None,
        *,
        max_depth: int = _DEFAULT_MAX_DEPTH,
        max_items: int = _DEFAULT_MAX_ITEMS,
        include_stacktraces: bool = False,
    ) -> None:
        """Configure how values are reduced.

        Args:
            date_format: A :meth:`~datetime.datetime.strftime` format for
                datetimes; ISO 8601 when omitted.
            max_depth: How deeply nested a value may be before it is cut.
            max_items: How many items of one collection are kept.
            include_stacktraces: Whether an exception carries its traceback.
        """
        self.date_format: str | None = date_format
        self.max_depth: int = max_depth
        self.max_items: int = max_items
        self.include_stacktraces: bool = include_stacktraces

    def normalize(self, value: object) -> Normalized:
        """Reduce ``value`` to plain data."""
        return self._normalize(value, 0)

    def format_datetime(self, value: dt.datetime) -> str:
        """Render ``value`` with :attr:`date_format`, or as ISO 8601."""
        if self.date_format is None:
            return value.isoformat()
        return value.strftime(self.date_format)

    def _normalize(self, value: object, depth: int) -> Normalized:  # noqa: C901, PLR0911 — one case per kind of value
        if depth > self.max_depth:
            return f"Over {self.max_depth} levels deep, aborting normalization"
        match value:
            case Enum():
                return self._normalize(value.value, depth)  # pyright: ignore[reportAny] — an enum's value is whatever it was declared with
            case None | bool() | int() | str():
                return value
            case float():
                return _float(value)
            case dt.datetime():
                return self.format_datetime(value)
            case dt.date() | dt.time():
                return value.isoformat()
            case BaseException():
                return self._normalize_exception(value, depth)
            case bytes() | bytearray():
                return bytes(value).decode("utf-8", "backslashreplace")
            case Mapping():
                return self._normalize_mapping(value, depth)  # pyright: ignore[reportUnknownArgumentType]
            case list() | tuple() | set() | frozenset():
                return self._normalize_items(value, depth)  # pyright: ignore[reportUnknownArgumentType]
            case _ if dataclasses.is_dataclass(value) and not isinstance(value, type):
                fields: dict[object, object] = {
                    field.name: getattr(value, field.name) for field in dataclasses.fields(value)
                }
                return {_class_name(value): self._normalize_mapping(fields, depth)}
            case _:
                return _describe(value)

    def _normalize_mapping(self, value: Mapping[object, object], depth: int) -> Normalized:
        normalized: dict[str, Normalized] = {}
        for count, (key, item) in enumerate(value.items()):
            if count >= self.max_items:
                normalized["..."] = _over_limit(self.max_items, len(value))
                break
            normalized[str(key)] = self._normalize(item, depth + 1)
        return normalized

    def _normalize_items(
        self, value: list[object] | tuple[object, ...] | set[object] | frozenset[object], depth: int
    ) -> Normalized:
        normalized: list[Normalized] = []
        for count, item in enumerate(value):
            if count >= self.max_items:
                normalized.append(_over_limit(self.max_items, len(value)))
                break
            normalized.append(self._normalize(item, depth + 1))
        return normalized

    def _normalize_exception(self, error: BaseException, depth: int) -> Normalized:
        """Describe ``error`` as its class, message, origin and cause."""
        described: dict[str, Normalized] = {
            "class": _class_name(error),
            "message": str(error),
        }
        frames = traceback.extract_tb(error.__traceback__)
        if frames:
            described["file"] = f"{frames[-1].filename}:{frames[-1].lineno}"
        if self.include_stacktraces and frames:
            described["trace"] = [f"{frame.filename}:{frame.lineno}" for frame in frames]
        previous = _previous(error)
        if previous is not None:
            described["previous"] = self._normalize(previous, depth + 1)
        return described


def _float(value: float) -> Normalized:
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "INF" if value > 0 else "-INF"
    return value


def _previous(error: BaseException) -> BaseException | None:
    if error.__cause__ is not None:
        return error.__cause__
    return None if error.__suppress_context__ else error.__context__


def _class_name(value: object) -> str:
    kind = type(value)
    if kind.__module__ == "builtins":
        return kind.__qualname__
    return f"{kind.__module__}.{kind.__qualname__}"


def _describe(value: object) -> str:
    """Use ``str()`` when the class defines one; otherwise name the class."""
    kind = type(value)
    if kind.__str__ is not object.__str__ or kind.__repr__ is not object.__repr__:
        return str(value)
    return f"[object {_class_name(value)}]"


def _over_limit(limit: int, total: int) -> str:
    return f"Over {limit} items ({total} total), aborting normalization"
