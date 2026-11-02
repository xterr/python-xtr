"""Where a value and the copy read back from it first differ, in value or in exact type."""

from __future__ import annotations

from collections import Counter, OrderedDict, deque
from dataclasses import fields, is_dataclass, make_dataclass
from datetime import datetime
from enum import Enum
from functools import cached_property, lru_cache
from inspect import getattr_static
from itertools import repeat
from operator import eq
from types import FunctionType
from typing import TYPE_CHECKING, Final, cast

from pydantic import BaseModel, RootModel

from ._part_pairs import ABSENT, PLAIN, mapping_pairs, pairs, set_pairs

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
    from types import CodeType
    from typing import TypeAlias

    from _typeshed import DataclassInstance
    from pydantic.fields import FieldInfo

    from ._part_pairs import Pair

    # The pairs of parts of one value still to compare, how many steps lead to the value, whether
    # its parts have a place in a path, the type a difference inside it is reported as, and the
    # value itself.
    _Frame: TypeAlias = tuple[Iterator[Pair], int, bool, type | None, object]

__all__ = ["first_difference"]

# The classes whose equality pydantic writes, comparing a model's fields as the walk does.
_PYDANTIC_EQUALITIES: Final = (BaseModel, RootModel)

# The containers looked into, of whatever subclass, and the classes whose equality compares
# what they hold as the walk does — or less strictly, as a counter's, which takes a key it lacks
# for zero —, so that the walk stands for it.
_CONTAINERS: Final[tuple[type, ...]] = (list, tuple, deque, dict, set, frozenset)
_WALKED_EQUALITIES: Final = frozenset({*_CONTAINERS, OrderedDict, Counter})


def first_difference(
    value: object, read: object, steps: list[str | int], *, by_alias: bool
) -> type | None:
    """Give the type of the first part of ``value`` that ``read`` does not give back, or ``None``.

    Parts are compared by exact type, then by value: an ``int`` field gives back ``1`` for
    ``True`` and for an ``IntEnum`` member, equal and yet another value. The one change allowed
    is the one a declared type makes on purpose: a ``datetime`` subclass, such as a ``DatePoint``,
    read back as a ``datetime``. Lists, tuples, dicts, sets, models and dataclasses are looked
    into, and deques, and the containers of a subclass of any of them — a named tuple by its
    fields, an ordered dict in its order —, an enum member excepted; any other value is compared
    as a whole. A model or a dataclass is looked into by the fields it declares and the extra
    fields pydantic keeps for it, never by whatever else its
    instance holds, such as what a cached property stored. What looking into it passes over is
    compared where it sits, on that object alone: an equality of its own — a model overriding
    the one pydantic writes, a dataclass comparing by any but the one ``dataclass`` generates,
    which compare the fields the walk compares and are not run — or else a model's private
    attributes. The walk keeps the parts still to compare in a list of its own rather than on the
    call stack, so no depth of the value, and no depth of the stack it is called from, makes it
    run out of stack; only an equality of an object's own may look deeper, as its class wrote it
    to.

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
            pending, depth, placed, report, _ = frames[-1]
            # The parts of the value on top, until one has parts of its own to compare first.
            for step, part, read_part, reported_as in pending:
                if placed and step is not None:
                    steps[depth:] = (step,)
                kind = type(part)
                if kind in PLAIN and type(read_part) is kind:
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


def _compare(value: object, read: object) -> type | Iterator[Pair] | None:
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
        return pairs(range(len(parts)), parts, read_parts) if same_size else kind
    if kind is dict:
        return mapping_pairs(
            cast("dict[object, object]", value), cast("dict[object, object]", read)
        )
    if kind is set or kind is frozenset:
        return set_pairs(cast("set[object]", value), cast("set[object]", read), kind)
    if isinstance(value, BaseModel) or is_dataclass(value):
        return _object_pairs(value, read)
    return _subclass_pairs(value, read, kind)


def _subclass_pairs(value: object, read: object, kind: type) -> type | Iterator[Pair] | None:
    """Compare a container of a subclass as its base is compared, its parts read by the base.

    The base's own methods read the parts, so no override of the subclass runs; an equality of
    the subclass's own, which the walk does not stand for, is compared where it sits first. A
    named tuple places its parts by its fields; an ordered dict differs in the order of its keys.
    Any other value, an enum member that is a container too, is compared as a whole.
    """
    # Looked up in the class's bases rather than tested with issubclass, whose narrowing to a
    # generic class leaves its arguments unknown.
    base = next((base for base in _CONTAINERS if base in kind.__mro__), None)
    if base is None or isinstance(value, Enum):
        return None if value == read else kind
    owner = next(base for base in kind.__mro__ if "__eq__" in vars(base))
    # By the equality itself: the built-in containers' inequality does not run it.
    if owner not in _WALKED_EQUALITIES and not eq(value, read):
        return kind
    if base is dict:
        return _subclass_mapping_pairs(value, read, kind)
    iterate = cast("Callable[[object], Iterator[object]]", vars(base)["__iter__"])
    parts, read_parts = list(iterate(value)), list(iterate(read))
    if base is set or base is frozenset:
        return set_pairs(set(parts), set(read_parts), kind)
    names = cast("object", getattr_static(kind, "_fields", None))
    named = base is tuple and isinstance(names, tuple)
    places = cast("tuple[str, ...]", names) if named else range(len(parts))
    same_size = len(parts) == len(read_parts)
    return pairs(cast("Sequence[str | int]", places), parts, read_parts) if same_size else kind


def _subclass_mapping_pairs(
    value: object, read: object, kind: type
) -> type | Iterator[Pair] | None:
    """Compare a mapping of a subclass as a dict, and an ordered one in the order of its keys.

    An ordered dict keeps its order apart from the dict it is: it is read in its own.
    """
    ordered = OrderedDict in kind.__mro__
    items = cast(
        "Callable[[object], Iterable[tuple[object, object]]]",
        OrderedDict.items if ordered else dict.items,
    )
    mapping, read_mapping = dict(items(value)), dict(items(read))
    if ordered and list(mapping) != list(read_mapping):
        return kind
    return mapping_pairs(mapping, read_mapping, kind)


def _object_pairs(value: object, read: object) -> type | Iterator[Pair] | None:
    """Compare a model or a dataclass where it sits, then pair its fields with their copies.

    Its fields are those it declares, then its extra fields: a copy holding an extra field
    ``value`` does not is reported as the object. A model stores its fields in its ``__dict__``,
    read there faster than attribute by attribute.
    """
    kind = type(value)
    if isinstance(value, BaseModel):
        model, read_model = value, cast("BaseModel", read)
        names = list(type(model).__pydantic_fields__)
        parts = list(map(model.__dict__.get, names, repeat(ABSENT)))
        read_parts = list(map(read_model.__dict__.get, names, repeat(ABSENT)))
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
    return pairs(
        [*names, *extra],
        [*parts, *extra.values()],
        [*read_parts, *map(read_extra.get, extra, repeat(ABSENT))],
    )


def _has_own_equality(kind: type) -> bool:
    """Whether ``kind`` compares by an equality other than a field by field one.

    pydantic writes a model's equality, comparing the fields. ``dataclass`` generates one too,
    unless told not to or the class writes its own, which it then keeps: an equality is taken as
    generated only when its code is that of the one ``dataclass`` generates for the same compared
    fields. Any other is the class's own.
    """
    owner = next(base for base in kind.__mro__ if "__eq__" in vars(base))
    if owner in _PYDANTIC_EQUALITIES:
        return False
    equality = cast("object", vars(owner)["__eq__"])
    if not getattr(vars(owner).get("__dataclass_params__"), "eq", False) or not isinstance(
        equality, FunctionType
    ):
        return True
    owned = cast("type[DataclassInstance]", owner)
    compared = tuple(field.name for field in fields(owned) if field.compare)
    code, generated = equality.__code__, _generated_equality(compared)
    return (code.co_code, code.co_names, code.co_consts, code.co_varnames) != (
        generated.co_code,
        generated.co_names,
        generated.co_consts,
        generated.co_varnames,
    )


# Bounded as the adapters are: classes built per call bring new field names each time.
@lru_cache(maxsize=256)
def _generated_equality(names: tuple[str, ...]) -> CodeType:
    """Give the code of the equality ``dataclass`` generates for fields named ``names``."""
    reference = make_dataclass("_", names, eq=True)
    return cast("FunctionType", vars(reference)["__eq__"]).__code__


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
        if name not in names and not isinstance(getattr_static(kind, name, None), cached_property)
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
