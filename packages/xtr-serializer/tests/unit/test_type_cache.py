"""A type cache builds a value once per type and scope, keeping those of the types used last."""

from __future__ import annotations

from itertools import count
from typing import Annotated

from xtr_serializer._type_cache import TypeCache


def counted() -> tuple[TypeCache[int], count[int]]:
    return TypeCache(), count(1)


def test_a_type_used_again_gives_the_value_built_for_it() -> None:
    cache, builds = counted()

    assert [cache.get(list[int], builds.__next__) for _ in range(3)] == [1, 1, 1]


def test_types_compared_unequal_get_values_of_their_own() -> None:
    cache, builds = counted()

    assert [cache.get(type_, builds.__next__) for type_ in (int | str, str | int)] == [1, 2]


def test_a_type_in_another_scope_gets_a_value_of_its_own() -> None:
    cache, builds = counted()

    values = [cache.get(int, builds.__next__, scope) for scope in ("json", "memory", "json")]

    assert values == [1, 2, 1]


def test_a_type_that_cannot_be_hashed_is_built_every_time() -> None:
    cache, builds = counted()
    unhashable = Annotated[int, []]

    assert [cache.get(unhashable, builds.__next__) for _ in range(2)] == [1, 2]


def test_it_keeps_the_values_of_the_last_256_types_used() -> None:
    cache, builds = counted()
    types = [Annotated[int, number] for number in range(257)]
    for type_ in types:
        _ = cache.get(type_, builds.__next__)

    assert (len(cache), cache.get(types[0], builds.__next__)) == (256, 258)
