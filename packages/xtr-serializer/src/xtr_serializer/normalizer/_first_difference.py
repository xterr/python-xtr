"""Where a value and the copy read back from it first differ, in value or in exact type."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime
from itertools import repeat
from typing import TYPE_CHECKING, Final, cast

from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["first_difference"]

# What a mapping holds at a key it lacks: of no type a value has, so it always differs.
_ABSENT: Final = object()

# The types whose values compare by the built-in comparison, with nothing inside to look into.
_PLAIN: Final = frozenset({str, int, float, bool, type(None)})


def first_difference(value: object, read: object, steps: list[str | int]) -> type | None:
    """Give the type of the first part of ``value`` that ``read`` does not give back, or ``None``.

    Parts are compared by exact type, then by value: an ``int`` field gives back ``1`` for
    ``True`` and for an ``IntEnum`` member, equal and yet another value. The one change allowed
    is the one a declared type makes on purpose: a ``datetime`` subclass, such as a ``DatePoint``,
    read back as a ``datetime``. Lists, tuples, dicts, sets, models and dataclasses are looked
    into; any other value is compared as a whole.

    ``steps`` is left holding the indexes, keys and attribute names leading to the part found, or
    to the part being compared when a comparison raises. A set has no place for its members, nor
    a mapping for a key that is not text or an integer: the steps stop at them.
    """
    kind = type(value)
    if type(read) is not kind and not (issubclass(kind, datetime) and type(read) is datetime):
        return kind
    if kind is list or kind is tuple:
        parts, read_parts = cast("list[object]", value), cast("list[object]", read)
        same_size = len(parts) == len(read_parts)
        return _first_of(range(len(parts)), parts, read_parts, steps) if same_size else kind
    if kind is dict:
        return _mapping_difference(
            cast("dict[object, object]", value), cast("dict[object, object]", read), steps
        )
    if kind is set or kind is frozenset:
        return _set_difference(cast("set[object]", value), cast("set[object]", read))
    if isinstance(value, BaseModel) or is_dataclass(value):
        return _first_of(*_attributes(value, read), steps)
    return None if value == read else kind


def _attributes(value: object, read: object) -> tuple[list[str], list[object], list[object]]:
    """Give the attribute names of a dataclass or a model, their values and their copies.

    A model stores its fields in its ``__dict__``, read there faster than attribute by attribute.
    """
    if is_dataclass(value):
        names = [field.name for field in fields(value)]
        return (
            names,
            [getattr(value, name) for name in names],
            [getattr(read, name) for name in names],
        )
    stored, read_stored = cast("BaseModel", value).__dict__, cast("BaseModel", read).__dict__
    names = list(stored)
    return names, list(stored.values()), list(map(read_stored.get, names, repeat(_ABSENT)))


def _first_of(
    places: Sequence[str | int],
    parts: list[object],
    read_parts: list[object],
    steps: list[str | int],
) -> type | None:
    """Compare each part with its copy, stepping into it, and stop at the first that differs.

    Parts all plain, of the same types and equal are settled at once, without a call per part.
    """
    kinds = list(map(type, parts))
    if _PLAIN.issuperset(kinds) and kinds == list(map(type, read_parts)) and parts == read_parts:
        return None
    for step, part, read_part in zip(places, parts, read_parts, strict=True):
        steps.append(step)
        if (difference := first_difference(part, read_part, steps)) is not None:
            return difference
        _ = steps.pop()
    return None


def _mapping_difference(
    value: dict[object, object], read: dict[object, object], steps: list[str | int]
) -> type | None:
    """Compare the keys, by exact type too, then what each key holds."""
    keys, read_keys = list(value), list(read)
    if len(keys) != len(read_keys):
        return dict
    if keys == read_keys and list(map(type, keys)) == list(map(type, read_keys)):
        # A key of another type has no place in a path: what it holds is compared at the mapping.
        places = [key for key in keys if type(key) is str or type(key) is int]
        if len(places) == len(keys):
            parts = list(value.values())
            return _first_of(places, parts, list(read.values()), steps)
    copies = {key: key for key in read_keys}
    for key, part in value.items():
        read_key = copies.get(key, _ABSENT)
        if first_difference(key, read_key, []) is not None:
            return dict
        if (difference := first_difference(part, read[read_key], [])) is not None:
            return difference
    return None


def _set_difference(value: set[object], read: set[object]) -> type | None:
    """Pair each member with the equal one read back, and compare their types and parts."""
    if len(value) != len(read):
        return type(value)
    members = {member: member for member in read}
    for member in value:
        if (difference := first_difference(member, members.get(member, _ABSENT), [])) is not None:
            return difference
    return None
