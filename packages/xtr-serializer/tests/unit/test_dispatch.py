"""A dispatch finds the first normalizer for a type, asking each only as often as it has to."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from tests.support.counting_normalizer import CountingNormalizer
from tests.support.in_memory_encoder import MEMORY
from tests.support.shapes import Point
from xtr_serializer._dispatch import Dispatch

if TYPE_CHECKING:
    from xtr_serializer import SupportedTypes


@dataclass(frozen=True, slots=True)
class Spot(Point):
    """A subclass of a point, which a key naming the point covers."""


def counting(name: str, supported: SupportedTypes, *, handles: bool = True) -> CountingNormalizer:
    return CountingNormalizer(name, {None: supported}, handles=handles)


def asks(candidate: CountingNormalizer) -> bool:
    return candidate.supports_normalization(None)


def first_of(dispatch: Dispatch[CountingNormalizer], type_: object, calls: int = 1) -> list[str]:
    """Look ``type_`` up ``calls`` times, naming what was found each time."""
    found = [dispatch.first(type_, None, asks) for _ in range(calls)]
    return [candidate.name if candidate else "" for candidate in found]


def test_an_answer_resting_on_the_type_alone_is_asked_for_once() -> None:
    normalizer = counting("n", {Point: True})

    assert first_of(Dispatch([normalizer]), Point, calls=3) == ["n"] * 3
    assert normalizer.asked == 1


def test_an_answer_resting_on_more_than_the_type_is_asked_for_every_time() -> None:
    normalizer = counting("n", {Point: False})

    assert first_of(Dispatch([normalizer]), Point, calls=3) == ["n"] * 3
    assert normalizer.asked == 3


def test_a_type_marked_not_handled_is_never_asked_for_even_under_a_broader_key() -> None:
    refusing = counting("refusing", {Point: None, "*": True})

    assert first_of(Dispatch([refusing, counting("next", {"*": True})]), Point) == ["next"]
    assert refusing.asked == 0


def test_a_type_no_key_covers_is_never_asked_for() -> None:
    normalizer = counting("n", {Spot: True})

    assert first_of(Dispatch([normalizer]), Point) == [""]
    assert normalizer.asked == 0


def test_a_key_naming_a_class_covers_its_subclasses() -> None:
    assert first_of(Dispatch([counting("n", {Point: True})]), Spot) == ["n"]


def test_a_key_naming_a_class_wins_over_a_broader_one() -> None:
    normalizer = counting("n", {"*": True, Point: False})

    _ = first_of(Dispatch([normalizer]), Point, calls=2)

    assert normalizer.asked == 2


def test_the_object_key_covers_classes_but_not_other_types() -> None:
    dispatch = Dispatch([counting("n", {"object": True})])

    assert [*first_of(dispatch, Point), *first_of(dispatch, list[Point])] == ["n", ""]


def test_the_star_key_covers_any_type() -> None:
    assert first_of(Dispatch([counting("n", {"*": True})]), int | None) == ["n"]


def test_a_normalizer_saying_no_for_the_type_alone_is_not_asked_again() -> None:
    refusing = counting("refusing", {"*": True}, handles=False)

    assert first_of(Dispatch([refusing, counting("next", {"*": True})]), Point, 3) == ["next"] * 3
    assert refusing.asked == 1


def test_normalizers_after_the_one_found_for_the_type_alone_are_never_asked() -> None:
    later = counting("later", {"*": True})

    _ = first_of(Dispatch([counting("n", {"*": True}), later]), Point, calls=2)

    assert later.asked == 0


def test_answers_are_remembered_per_format() -> None:
    normalizer = CountingNormalizer("n", {MEMORY: {Point: True}})
    dispatch = Dispatch([normalizer])

    found = [dispatch.first(Point, format_, asks) for format_ in (MEMORY, "json", MEMORY)]

    assert [candidate.name if candidate else "" for candidate in found] == ["n", "", "n"]


def test_a_normalizer_asked_about_a_type_may_look_another_up() -> None:
    dispatch: Dispatch[CountingNormalizer] = Dispatch([counting("n", {"*": True})])

    def asks_about_another(candidate: CountingNormalizer) -> bool:
        return dispatch.first(str, None, asks) is candidate

    assert dispatch.first(int, None, asks_about_another) is not None


def test_threads_looking_types_up_at_once_each_find_the_normalizer_for_theirs() -> None:
    names = [f"n{index}" for index in range(8)]
    types = [type(name, (), {}) for name in names]
    normalizers = [counting(name, {kind: True}) for name, kind in zip(names, types, strict=True)]
    dispatch = Dispatch(normalizers)
    found: list[list[str]] = [[] for _ in names]

    def look_up(index: int) -> None:
        found[index] = first_of(dispatch, types[index], calls=200)

    threads = [threading.Thread(target=look_up, args=(index,)) for index in range(len(names))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert found == [[name] * 200 for name in names]
