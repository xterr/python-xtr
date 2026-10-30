"""Where a value and the copy read back from it first differ, in value or in exact type."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime
from itertools import repeat
from typing import TYPE_CHECKING, Final, cast

from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from typing import TypeAlias

    from pydantic.fields import FieldInfo

    # Two parts to compare: the step leading to them, or ``None`` where they have no place in a
    # path; the part; its copy; and the type a difference inside them is reported as, ``None``
    # for the type of the part that differs.
    _Pair: TypeAlias = tuple[str | int | None, object, object, type | None]

    # The pairs of parts of one value still to compare, how many steps lead to the value, whether
    # its parts have a place in a path, the type a difference inside it is reported as, and the
    # value itself.
    _Frame: TypeAlias = tuple[Iterator[_Pair], int, bool, type | None, object]

__all__ = ["first_difference"]

# What a mapping holds at a key it lacks: of no type a value has, so it always differs.
_ABSENT: Final = object()

# The types whose values compare by the built-in comparison, with nothing inside to look into.
_PLAIN: Final = frozenset({str, int, float, bool, type(None)})


def first_difference(
    value: object, read: object, steps: list[str | int], *, by_alias: bool
) -> type | None:
    """Give the type of the first part of ``value`` that ``read`` does not give back, or ``None``.

    Parts are compared by exact type, then by value: an ``int`` field gives back ``1`` for
    ``True`` and for an ``IntEnum`` member, equal and yet another value. The one change allowed
    is the one a declared type makes on purpose: a ``datetime`` subclass, such as a ``DatePoint``,
    read back as a ``datetime``. Lists, tuples, dicts, sets, models and dataclasses are looked
    into; any other value is compared as a whole. A model or a dataclass may define an equality
    of its own, which looking into it passes over: when the walk has looked into one and found
    no difference, the two values are compared as a whole too, and ``value`` is the part found
    if they differ. The walk keeps the parts still to compare in a list of its own rather than
    on the call stack, so no depth of the value, and no depth of the stack it is called from,
    makes it run out of stack.

    ``steps`` is left holding the indexes, keys and field names leading to the part found, or to
    the part being compared when a comparison raises. A field is named as it is written: by its
    alias when ``by_alias`` holds and pydantic records one, as it does for the fields of a model
    and of a dataclass it built. A set has no place for its members, nor a mapping for a key that
    is not text or an integer: the steps stop at them.
    """
    objects: list[object] = []
    found = _compare(value, read, objects)
    if isinstance(found, type):
        return found
    frames: list[_Frame] = [] if found is None else [(found, 0, True, None, value)]
    try:
        while frames:
            pairs, depth, placed, report, _ = frames[-1]
            # The parts of the value on top, until one has parts of its own to compare first.
            for step, part, read_part, reported_as in pairs:
                if placed and step is not None:
                    steps[depth:] = (step,)
                kind = type(part)
                if kind in _PLAIN and type(read_part) is kind:
                    found = None if part == read_part else kind
                else:
                    found = _compare(part, read_part, objects)
                if found is None:
                    continue
                part_report = reported_as if report is None else report
                if isinstance(found, type):
                    return found if part_report is None else part_report
                frames.append((found, len(steps), placed and step is not None, part_report, part))
                break
            else:
                _ = frames.pop()
    finally:
        # Named only once the walk has stopped, where it stopped: most values differ nowhere.
        if by_alias:
            _name_by_alias(steps, frames)
    steps.clear()
    return type(value) if objects and value != read else None


def _compare(value: object, read: object, objects: list[object]) -> type | Iterator[_Pair] | None:
    """Compare ``value`` with its copy as far as can be done at once.

    Gives the type of ``value`` where the two differ, ``None`` where they are equal, and else
    the pairs of their parts to compare next. A model or a dataclass looked into is added to
    ``objects``.
    """
    kind = type(value)
    if type(read) is not kind and not (issubclass(kind, datetime) and type(read) is datetime):
        return kind
    if kind is list or kind is tuple:
        parts, read_parts = cast("list[object]", value), cast("list[object]", read)
        same_size = len(parts) == len(read_parts)
        return _pairs(range(len(parts)), parts, read_parts) if same_size else kind
    if kind is dict:
        return _mapping_pairs(
            cast("dict[object, object]", value), cast("dict[object, object]", read)
        )
    if kind is set or kind is frozenset:
        return _set_pairs(cast("set[object]", value), cast("set[object]", read))
    if isinstance(value, BaseModel) or is_dataclass(value):
        objects.append(value)
        return _pairs(*_attributes(value, read))
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


def _name_by_alias(steps: list[str | int], frames: list[_Frame]) -> None:
    """Rename each field in ``steps`` by the alias it is written under, where pydantic records one.

    ``frames`` holds the values the steps lead through. pydantic records the fields of a model
    and of a dataclass it built on the class itself, aliases included, whether declared or
    generated; the fields of another class keep their names.
    """
    for _, depth, placed, _, owner in frames:
        if placed and depth < len(steps) and (isinstance(owner, BaseModel) or is_dataclass(owner)):
            recorded = cast("object", vars(type(owner)).get("__pydantic_fields__", {}))
            info = cast("dict[str, FieldInfo]", recorded).get(cast("str", steps[depth]))
            if info is not None and info.serialization_alias is not None:
                steps[depth] = info.serialization_alias


def _pairs(
    places: Sequence[str | int], parts: list[object], read_parts: list[object]
) -> Iterator[_Pair] | None:
    """Pair each part with its copy, at its place.

    Parts all plain, of the same types and equal are settled at once, without a step per part.
    """
    kinds = list(map(type, parts))
    if _PLAIN.issuperset(kinds) and kinds == list(map(type, read_parts)) and parts == read_parts:
        return None
    return zip(places, parts, read_parts, repeat(None), strict=False)  # the last never ends


def _mapping_pairs(
    value: dict[object, object], read: dict[object, object]
) -> type | Iterator[_Pair] | None:
    """Compare the keys, by exact type too, then pair what each key holds."""
    keys, read_keys = list(value), list(read)
    if len(keys) != len(read_keys):
        return dict
    if keys == read_keys and list(map(type, keys)) == list(map(type, read_keys)):
        # A key of another type has no place in a path: what it holds is compared at the mapping.
        places = [key for key in keys if type(key) is str or type(key) is int]
        if len(places) == len(keys):
            return _pairs(places, list(value.values()), list(read.values()))
    return _keyed_pairs(value, read, read_keys)


def _keyed_pairs(
    value: dict[object, object], read: dict[object, object], read_keys: list[object]
) -> Iterator[_Pair]:
    """Pair each key with the equal one read back, then what the two hold, all at the mapping.

    A key that differs is reported as the mapping that holds it.
    """
    copies = {key: key for key in read_keys}
    for key, part in value.items():
        read_key = copies.get(key, _ABSENT)
        yield None, key, read_key, dict
        yield None, part, read[read_key], None


def _set_pairs(value: set[object], read: set[object]) -> type | Iterator[_Pair]:
    """Pair each member with the equal one read back, to compare their types and parts."""
    if len(value) != len(read):
        return type(value)
    members = {member: member for member in read}
    return ((None, member, members.get(member, _ABSENT), None) for member in value)
