"""pydantic's validation errors, as this package's errors, without the values."""

from __future__ import annotations

from inspect import getattr_static
from types import MemberDescriptorType
from typing import TYPE_CHECKING, Final, cast

from xtr_serializer._loc_path import render_path
from xtr_serializer.exception import ExtraAttributesError, NotNormalizableValueError

if TYPE_CHECKING:
    from pydantic_core import ErrorDetails

__all__ = ["refusals_of"]

# How pydantic reports a field the data has and the type does not declare: for a model or a
# typed dict, and for a dataclass.
_EXTRA: Final = frozenset({"extra_forbidden", "unexpected_keyword_argument"})

# The errors whose message pydantic builds from the data — a union's tag, what an object raised
# as it was read, a time zone, a byte unit or an import path it could not make out — said in words
# of their own. The others describe the type; the most they let through is a count of items, or
# the one character a UUID stops parsing at. Or they are a validator's: its message is the words
# of the application that wrote it, not the data's, and is passed on as written.
_FIXED_MESSAGES: Final = {
    "union_tag_invalid": "Input tag does not match any of the expected tags",
    "bytes_invalid_encoding": "Data should be valid in its declared encoding",
    "get_attribute_error": "Error extracting attribute",
    "iteration_error": "Error iterating over object",
    "mapping_type": "Input should be a valid mapping",
    "datetime_object_invalid": "Invalid datetime object",
    "timezone_offset": "Timezone offset does not match the one required",
    "zoneinfo_str": "invalid timezone",
    "byte_size_unit": "could not interpret byte unit",
    "import_error": "Invalid python path",
}

# What pydantic puts after a mapping key it refused.
_KEY: Final = "[key]"

# What a step finds when the value does not hold it, and when the value holds it behind code of
# the data's own — a property, a descriptor — that the walk does not run.
_ABSENT: Final = object()
_OPAQUE: Final = object()


def refusals_of(details: list[ErrorDetails], data: object) -> list[NotNormalizableValueError]:
    """Turn pydantic's errors about ``data`` into this package's, in pydantic's order.

    Each keeps pydantic's message, which describes the type rather than the value — or words of
    its own where pydantic's quote the data —, its error type, the name of the type the value
    had, and where it sits in ``data``. The message of a validator — a ``ValueError``, an
    assertion, a ``PydanticCustomError`` it raised — is kept as the validator worded it, which is
    why a validator must not quote the value it refuses. pydantic also names the union member it
    tried and marks a refused key; the path leaves out both, and the refused key itself, which is
    the value.

    pydantic reports each field an object should not have on its own; they are reported as one
    error naming them all, where the first of them was, as a reader would want to hear about a
    misspelled object. An error pydantic reports once per union member it tried is reported once.

    ``data`` is walked without running any of its code: a dict or a list is looked into as one,
    whatever its class overrides, a key is matched only by a key of the step's own built-in type,
    and an object is looked into only through the attributes it stores. A step held behind a
    property ends the path there.
    """
    located = [(detail, _steps(detail, data)) for detail in details]
    extras: dict[str | None, list[str]] = {}
    for detail, steps in located:
        if detail["type"] in _EXTRA:
            extras.setdefault(render_path(steps[:-1]), []).append(str(detail["loc"][-1]))
    refusals: list[NotNormalizableValueError] = []
    reported: set[tuple[str | None, str, str]] = set()
    for detail, steps in located:
        error_type = detail["type"]
        if error_type in _EXTRA:
            path = render_path(steps[:-1])
            if (names := extras.pop(path, None)) is not None:
                refusals.append(
                    ExtraAttributesError(tuple(names), path=path, error_type=error_type)
                )
            continue
        path = render_path(steps)
        message = _FIXED_MESSAGES.get(error_type, detail["msg"])
        if detail["loc"][-1:] == (_KEY,):
            message = f"a key: {message}"
        if (path, error_type, message) in reported:
            continue
        reported.add((path, error_type, message))
        # A missing field's input is the object it is missing from.
        current_type = (
            None if error_type == "missing" else type(cast("object", detail["input"])).__name__
        )
        refusals.append(
            NotNormalizableValueError(
                message,
                path=path,
                current_type=current_type,
                error_type=error_type,
            )
        )
    return refusals


def _steps(detail: ErrorDetails, data: object) -> list[str | int]:
    """Keep the keys and indexes of the error's location that lead through ``data``.

    A step the data does not hold names the union member pydantic tried, unless it is the last
    one of a field the data lacks. A refused key is left out with its marker. The walk stops at
    a value it cannot look into, keeping the steps that led there.
    """
    loc = detail["loc"]
    if loc[-1:] == (_KEY,):
        loc = loc[:-2]
    steps: list[str | int] = []
    current = data
    for index, step in enumerate(loc, start=1):
        if current is _OPAQUE:
            break
        found = _value_at(current, step)
        if found is not _ABSENT:
            steps.append(step)
            current = found
        elif index == len(loc) and detail["type"] == "missing":
            steps.append(step)
    return steps


def _value_at(value: object, step: str | int) -> object:
    """Find what ``value`` holds at ``step`` as a key, an index or a stored attribute.

    The built-in lookups are called directly, so a subclass overriding them is not run. A key is
    compared only when it has the step's exact type, whose comparison is the built-in one: looking
    the step up by hash would compare it with any key sharing that hash, running that key's code.
    """
    kind = type(value)
    if issubclass(kind, dict):
        items = dict[object, object].items(cast("dict[object, object]", value))
        return next(
            (item for key, item in items if type(key) is type(step) and key == step), _ABSENT
        )
    if issubclass(kind, list | tuple):
        items = _items_of(cast("list[object] | tuple[object, ...]", value))
        return items[step] if isinstance(step, int) and 0 <= step < len(items) else _ABSENT
    if value is None or issubclass(kind, str | bytes | int | float) or not isinstance(step, str):
        return _ABSENT
    return _attribute_at(value, step)


def _items_of(value: list[object] | tuple[object, ...]) -> list[object] | tuple[object, ...]:
    """Give a plain list or tuple of the items, copied by the built-in when a subclass holds them.

    Data read as JSON holds plain ones, indexed as they are.
    """
    if type(value) is list or type(value) is tuple:
        return value
    if issubclass(type(value), list):
        return list[object].copy(cast("list[object]", value))
    return tuple[object, ...].__getitem__(cast("tuple[object, ...]", value), slice(None))


def _attribute_at(value: object, step: str) -> object:
    """Find the attribute ``step`` that ``value`` stores, or :data:`_OPAQUE` behind code."""
    attribute = cast("object", getattr_static(value, step, _ABSENT))
    if type(attribute) is MemberDescriptorType:  # a slot, read by the interpreter alone
        try:
            return cast("object", attribute.__get__(value))
        except AttributeError:  # a slot never set
            return _ABSENT
    if getattr_static(type(attribute), "__get__", _ABSENT) is not _ABSENT:
        return _OPAQUE
    return attribute
