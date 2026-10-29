"""pydantic's validation errors, as this package's errors, without the values."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from inspect import getattr_static
from typing import TYPE_CHECKING, Final, cast

from xtr_serializer._loc_path import render_path
from xtr_serializer.exception import ExtraAttributesError, NotNormalizableValueError

if TYPE_CHECKING:
    from pydantic_core import ErrorDetails

__all__ = ["refusals_of"]

# How pydantic reports a field the data has and the type does not declare: for a model or a
# typed dict, and for a dataclass.
_EXTRA: Final = frozenset({"extra_forbidden", "unexpected_keyword_argument"})

# The errors whose message pydantic builds from the data — a union's tag, a validator's own
# words, what an object raised as it was read — said in words of their own. The others describe
# the type; the most they let through is a count of items, or the one character a UUID stops
# parsing at.
_FIXED_MESSAGES: Final = {
    "union_tag_invalid": "Input tag does not match any of the expected tags",
    "bytes_invalid_encoding": "Data should be valid in its declared encoding",
    "value_error": "Value error",
    "assertion_error": "Assertion failed",
    "get_attribute_error": "Error extracting attribute",
    "iteration_error": "Error iterating over object",
    "mapping_type": "Input should be a valid mapping",
    "datetime_object_invalid": "Invalid datetime object",
    "timezone_offset": "Timezone offset does not match the one required",
}

# What pydantic puts after a mapping key it refused.
_KEY: Final = "[key]"

_ABSENT: Final = object()


def refusals_of(details: list[ErrorDetails], data: object) -> list[NotNormalizableValueError]:
    """Turn pydantic's errors about ``data`` into this package's, in pydantic's order.

    Each keeps pydantic's message, which describes the type rather than the value — or words of
    its own where pydantic's quote the data —, its error type, the name of the type the value
    had, and where it sits in ``data``. pydantic also names the union member it tried and marks a
    refused key; the path leaves out both, and the refused key itself, which is the value.

    pydantic reports each field an object should not have on its own; they are reported as one
    error naming them all, where the first of them was, as a reader would want to hear about a
    misspelled object. An error pydantic reports once per union member it tried is reported once.
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
    one of a field the data lacks. A refused key is left out with its marker.
    """
    loc = detail["loc"]
    if loc[-1:] == (_KEY,):
        loc = loc[:-2]
    steps: list[str | int] = []
    current = data
    for index, step in enumerate(loc, start=1):
        if _holds(current, step):
            steps.append(step)
            if index < len(loc):  # an object's attribute is read only on the way to another
                current = _value_at(current, step)
        elif index == len(loc) and detail["type"] == "missing":
            steps.append(step)
    return steps


def _holds(value: object, step: str | int) -> bool:
    """Tell whether ``value`` has ``step`` as a key, an index or an attribute, reading nothing."""
    if isinstance(value, Mapping):
        return step in cast("Mapping[object, object]", value)
    if isinstance(value, list | tuple):
        return isinstance(step, int) and 0 <= step < len(cast("Sequence[object]", value))
    return isinstance(step, str) and getattr_static(value, step, _ABSENT) is not _ABSENT


def _value_at(value: object, step: str | int) -> object:
    """Read what ``value`` holds at ``step``, which :func:`_holds` found there."""
    if isinstance(value, Mapping):
        return cast("Mapping[object, object]", value)[step]
    if isinstance(step, int):
        return cast("Sequence[object]", value)[step]
    return cast("object", getattr(value, step))
