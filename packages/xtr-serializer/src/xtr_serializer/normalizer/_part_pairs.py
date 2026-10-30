"""The parts of a container paired with their copies, for the read-back comparison to walk."""

from __future__ import annotations

from itertools import repeat
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from typing import TypeAlias

    # Two parts to compare: the step leading to them, or ``None`` where they have no place in a
    # path; the part; its copy; and the type a difference inside them is reported as, ``None``
    # for the type of the part that differs.
    Pair: TypeAlias = tuple[str | int | None, object, object, type | None]

__all__ = ["ABSENT", "PLAIN", "mapping_pairs", "pairs", "set_pairs"]

# What a mapping holds at a key it lacks: of no type a value has, so it always differs.
ABSENT: Final = object()

# The types whose values compare by the built-in comparison, with nothing inside to look into.
PLAIN: Final = frozenset({str, int, float, bool, type(None)})


def pairs(
    places: Sequence[str | int], parts: list[object], read_parts: list[object]
) -> Iterator[Pair] | None:
    """Pair each part with its copy, at its place.

    Parts all plain, of the same types and equal are settled at once, without a step per part.
    """
    kinds = list(map(type, parts))
    if PLAIN.issuperset(kinds) and kinds == list(map(type, read_parts)) and parts == read_parts:
        return None
    return zip(places, parts, read_parts, repeat(None), strict=False)  # the last never ends


def mapping_pairs(
    value: dict[object, object], read: dict[object, object], kind: type = dict
) -> type | Iterator[Pair] | None:
    """Compare the keys, by exact type too, then pair what each key holds.

    ``kind`` is the type of the mapping the two were read from, a difference in keys reported as.
    """
    keys, read_keys = list(value), list(read)
    if len(keys) != len(read_keys):
        return kind
    if keys == read_keys and list(map(type, keys)) == list(map(type, read_keys)):
        # A key of another type has no place in a path: what it holds is compared at the mapping.
        places = [key for key in keys if type(key) is str or type(key) is int]
        if len(places) == len(keys):
            return pairs(places, list(value.values()), list(read.values()))
    return _keyed_pairs(value, read, read_keys, kind)


def _keyed_pairs(
    value: dict[object, object], read: dict[object, object], read_keys: list[object], kind: type
) -> Iterator[Pair]:
    """Pair each key with the equal one read back, then what the two hold, all at the mapping.

    A key that differs is reported as the mapping that holds it.
    """
    copies = {key: key for key in read_keys}
    for key, part in value.items():
        read_key = copies.get(key, ABSENT)
        yield None, key, read_key, kind
        yield None, part, read[read_key], None


def set_pairs(value: set[object], read: set[object], kind: type) -> type | Iterator[Pair]:
    """Pair each member with the equal one read back, to compare their types and parts."""
    if len(value) != len(read):
        return kind
    members = {member: member for member in read}
    return ((None, member, members.get(member, ABSENT), None) for member in value)
