"""pydantic's validation errors, as this package's errors, without the values."""

from __future__ import annotations

from inspect import getattr_static
from types import MemberDescriptorType
from typing import TYPE_CHECKING, Final, TypeAlias, cast, final

from xtr_serializer._loc_path import render_path
from xtr_serializer._type_names import name_of
from xtr_serializer.exception import ExtraAttributesError, NotNormalizableValueError

from ._built_in_words import value_error_message

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic_core import ErrorDetails

    # What finds the item a mapping holds at a step of a location.
    _ItemAt: TypeAlias = Callable[[dict[object, object], str | int], object]

__all__ = ["refusals_of"]

# How pydantic reports a field the data has and the type does not declare: for a model or a
# typed dict, and for a dataclass.
_EXTRA: Final = frozenset({"extra_forbidden", "unexpected_keyword_argument"})

# The errors whose message pydantic builds from the data — a union's tag, what an object raised
# as it was read, a time zone, a byte unit or an import path it could not make out — said in words
# of their own. The others describe the type; the most they let through is a count of items, or
# the one character a UUID stops parsing at. Or they are a validator's: its message is the words
# of the application that wrote it, not the data's, and is passed on as written — a value error
# only when the application's code raised it, see value_error_message.
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


def refusals_of(
    details: list[ErrorDetails], data: object, *, plain: bool
) -> list[NotNormalizableValueError]:
    """Turn pydantic's errors about ``data`` into this package's, in pydantic's order.

    Each keeps pydantic's message, which describes the type rather than the value — or words of
    its own where pydantic's quote the data —, its error type, the name of the type the value
    had, read without running its metaclass, and where it sits in ``data``. The message of a
    validator — a ``ValueError``, an assertion, a ``PydanticCustomError`` it raised — is kept as
    the validator worded it, which is why a validator must not quote the value it refuses.
    A ``ValueError`` raised by the code reading a built-in type, such as an IP address or an
    email address, quotes the data: it is said in fixed words. ``details`` must carry their
    context for that, as ``ValidationError.errors`` gives it by default.
    pydantic also names the union member it tried and marks a refused key; the path leaves out
    both, and the refused key itself, which is the value.

    pydantic reports each field an object should not have on its own; they are reported as one
    error naming them all, where the first of them was, as a reader would want to hear about a
    misspelled object. An error pydantic reports once per union member it tried is reported once.

    ``data`` is walked without running any of its code: a dict or a list is looked into as one,
    whatever its class overrides, a key is matched only by a key of the step's own built-in type,
    and an object is looked into only through the attributes it stores. A step held behind a
    property ends the path there. ``plain`` says ``data`` is plain data, JSON as it is parsed or
    written, whose keys are all strings: a key is looked up there directly. In other data the
    keys of a mapping are indexed the first time the walk steps into it, so that locating every
    error of a large mapping takes about as long as reading it once.
    """
    item_at = _plain_item_at if plain else _KeyIndexes().item_at
    located = [(detail, _steps(detail, data, item_at)) for detail in details]
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
        if error_type == "value_error":
            message = value_error_message(detail)
        else:
            message = _FIXED_MESSAGES.get(error_type, detail["msg"])
        if detail["loc"][-1:] == (_KEY,):
            message = f"a key: {message}"
        if (path, error_type, message) in reported:
            continue
        reported.add((path, error_type, message))
        # A missing field's input is the object it is missing from.
        current_type = (
            None if error_type == "missing" else name_of(type(cast("object", detail["input"])))
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


def _steps(detail: ErrorDetails, data: object, item_at: _ItemAt) -> list[str | int]:
    """Keep the keys and indexes of the error's location that lead through ``data``.

    A step the data does not hold names the union member pydantic tried, unless it is the last
    one of a field the data lacks — such as the number a class hierarchy's union puts before the
    fields of the class it read, which no object's key is. A refused key is left out with its
    marker. The walk stops at a value it cannot look into, keeping the steps that led there.
    """
    loc = detail["loc"]
    if loc[-1:] == (_KEY,):
        loc = loc[:-2]
    steps: list[str | int] = []
    current = data
    for index, step in enumerate(loc, start=1):
        if current is _OPAQUE:
            break
        found = _value_at(current, step, item_at)
        if found is not _ABSENT:
            steps.append(step)
            current = found
        elif index == len(loc) and detail["type"] == "missing":
            steps.append(step)
    return steps


def _value_at(value: object, step: str | int, item_at: _ItemAt) -> object:
    """Find what ``value`` holds at ``step`` as a key, an index or a stored attribute.

    A mapping is looked into by ``item_at``; a list or a tuple by the built-in lookups, called
    directly, so a subclass overriding them is not run and nothing is copied.
    """
    kind = type(value)
    if issubclass(kind, dict):
        return item_at(cast("dict[object, object]", value), step)
    if isinstance(step, int):
        return _index_at(value, step)
    if value is None or issubclass(kind, list | tuple | str | bytes | int | float):
        return _ABSENT
    return _attribute_at(value, step)


def _index_at(value: object, index: int) -> object:
    """Find the item of a list or a tuple at ``index``; any other value holds none."""
    if issubclass(type(value), list):
        items = cast("list[object]", value)
        size = list[object].__len__(items)
        return list[object].__getitem__(items, index) if 0 <= index < size else _ABSENT
    if issubclass(type(value), tuple):
        members = cast("tuple[object, ...]", value)
        size = tuple[object, ...].__len__(members)
        return tuple[object, ...].__getitem__(members, index) if 0 <= index < size else _ABSENT
    return _ABSENT


def _plain_item_at(mapping: dict[object, object], step: str | int) -> object:
    """Find what a mapping of plain data holds at ``step``: its keys are all strings."""
    return mapping.get(step, _ABSENT)


@final
class _KeyIndexes:
    """The keys of each mapping the walk steps into, indexed once, by exact type.

    An index holds only the keys of a type a step has, ``str`` or ``int`` exactly, whose
    comparison is the built-in one: looking a step up in the mapping itself would compare it with
    any key sharing its hash, running that key's code.
    """

    __slots__ = ("_indexes",)

    def __init__(self) -> None:
        # By identity: each mapping is held by the data, which outlives the walk.
        self._indexes: dict[int, dict[str | int, object]] = {}

    def item_at(self, mapping: dict[object, object], step: str | int) -> object:
        """Find what ``mapping`` holds at ``step``, indexing its keys on the first lookup."""
        index = self._indexes.get(id(mapping))
        if index is None:
            items = dict[object, object].items(mapping)
            index = {key: item for key, item in items if type(key) is str or type(key) is int}
            self._indexes[id(mapping)] = index
        return index.get(step, _ABSENT)


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
