"""Where a value and the copy read back from it first differ, in value or in exact type."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime
from inspect import getattr_static
from itertools import repeat
from typing import TYPE_CHECKING, Final, cast

from pydantic import BaseModel, RootModel

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence
    from typing import TypeAlias

    from _typeshed import DataclassInstance
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

# The classes whose equality pydantic writes, comparing a model's fields as the walk does.
_PYDANTIC_EQUALITIES: Final = (BaseModel, RootModel)


def first_difference(
    value: object, read: object, steps: list[str | int], *, by_alias: bool
) -> type | None:
    """Give the type of the first part of ``value`` that ``read`` does not give back, or ``None``.

    Parts are compared by exact type, then by value: an ``int`` field gives back ``1`` for
    ``True`` and for an ``IntEnum`` member, equal and yet another value. The one change allowed
    is the one a declared type makes on purpose: a ``datetime`` subclass, such as a ``DatePoint``,
    read back as a ``datetime``. Lists, tuples, dicts, sets, models and dataclasses are looked
    into; any other value is compared as a whole. A model or a dataclass is looked into by the
    fields it declares and the extra fields pydantic keeps for it, never by whatever else its
    instance holds, such as what a cached property stored. What looking into it passes over is
    compared where it sits, on that object alone: an equality of its own — a model overriding
    the one pydantic writes, a dataclass turning off the one ``dataclass`` writes, which compare
    the fields the walk compares and are not run — or else a model's private attributes. The
    walk keeps the parts still to compare in a list of its own rather than on the call stack, so
    no depth of the value, and no depth of the stack it is called from, makes it run out of
    stack; only an equality of an object's own may look deeper, as its class wrote it to.

    ``steps`` is left holding the indexes, keys and field names leading to the part found, or to
    the part being compared when a comparison raises. A field is named as it is written: by its
    alias when ``by_alias`` holds and pydantic records one, as it does for the fields of a model
    and of a dataclass it built; a dataclass of the standard library keeps the names of its
    fields, even one its annotation gives an alias pydantic writes it under. A set has no place
    for its members, nor a mapping for a key that is not text or an integer: the steps stop at
    them.
    """
    found = _compare(value, read)
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
                    found = _compare(part, read_part)
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
    return None


def _compare(value: object, read: object) -> type | Iterator[_Pair] | None:
    """Compare ``value`` with its copy as far as can be done at once.

    Gives the type of ``value`` where the two differ, ``None`` where they are equal, and else
    the pairs of their parts to compare next.
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
        return _object_pairs(value, read)
    return None if value == read else kind


def _object_pairs(value: object, read: object) -> type | Iterator[_Pair] | None:
    """Compare a model or a dataclass where it sits, then pair its fields with their copies.

    Its fields are those it declares, then its extra fields: a copy holding an extra field
    ``value`` does not is reported as the object. A model stores its fields in its ``__dict__``,
    read there faster than attribute by attribute.
    """
    kind = type(value)
    if isinstance(value, BaseModel):
        model, read_model = value, cast("BaseModel", read)
        names = list(type(model).__pydantic_fields__)
        parts = list(map(model.__dict__.get, names, repeat(_ABSENT)))
        read_parts = list(map(read_model.__dict__.get, names, repeat(_ABSENT)))
        # Compared by pydantic's equality, which reads them as it is written.
        besides = model.__pydantic_private__ != read_model.__pydantic_private__
    else:
        names = [field.name for field in fields(cast("DataclassInstance", value))]
        parts = [getattr(value, name) for name in names]
        read_parts = [getattr(read, name) for name in names]
        besides = False
    extra, read_extra = _extra_fields(value, names), _extra_fields(read, names)
    if len(read_extra) > len(extra) or (value != read if _has_own_equality(kind) else besides):
        return kind
    return _pairs(
        [*names, *extra],
        [*parts, *extra.values()],
        [*read_parts, *map(read_extra.get, extra, repeat(_ABSENT))],
    )


def _has_own_equality(kind: type) -> bool:
    """Whether ``kind`` compares by an equality other than a field by field one.

    pydantic writes a model's equality, and ``dataclass`` a dataclass's unless told not to, each
    comparing the fields; any other is the class's own.
    """
    owner = next(base for base in kind.__mro__ if "__eq__" in vars(base))
    if owner in _PYDANTIC_EQUALITIES:
        return False
    return not getattr(vars(owner).get("__dataclass_params__"), "eq", False)


def _extra_fields(value: object, names: list[str]) -> dict[str, object]:
    """Give the fields pydantic keeps for an object beyond those it declares.

    A model keeps them apart; a dataclass whose configuration allows them, beside its fields: what
    its class names, such as a cached property, is the class's, not an extra field.
    """
    if isinstance(value, BaseModel):
        return value.__pydantic_extra__ or {}
    kind = type(value)
    config = cast("Mapping[str, object]", getattr(kind, "__pydantic_config__", {}))
    if config.get("extra") != "allow":
        return {}
    stored = cast("dict[str, object]", getattr(value, "__dict__", {}))
    return {
        name: part
        for name, part in stored.items()
        if name not in names and getattr_static(kind, name, _ABSENT) is _ABSENT
    }


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
