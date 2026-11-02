"""Where a value and its copy first differ, in value or in exact type."""

from __future__ import annotations

import inspect
import sys
from collections import Counter, OrderedDict, defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from functools import cached_property
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel, PrivateAttr, RootModel, TypeAdapter
from typing_extensions import override
from xtr_clock import DatePoint

from tests.fixtures.containers import Identical, Levelled, Members, Numbered, Rows
from tests.fixtures.equalities import GENERATED_EQUALITIES, HAND_WRITTEN_EQUALITIES, LabelledParcel
from tests.fixtures.exact_values import Extended, ExtendedParcel, Ledger, Level, Tally
from xtr_serializer.normalizer._first_difference import first_difference

if TYPE_CHECKING:
    from collections.abc import Callable


class Line(BaseModel):
    price: int


def difference(value: object, read: object) -> tuple[type | None, list[str | int]]:
    steps: list[str | int] = []
    return first_difference(value, read, steps, by_alias=True), steps


def at(kind: type, *steps: str | int) -> tuple[type, list[str | int]]:
    return kind, list(steps)


def test_equal_parts_of_the_same_types_have_no_difference() -> None:
    value: dict[object, object] = {"lines": [Line(price=1)], "tags": frozenset({"a"}), (1, 2): "p"}

    assert difference(value, {**value}) == (None, [])


@pytest.mark.parametrize(
    ("value", "read", "expected"),
    [
        pytest.param([1, True], [1, 1], at(bool, 1), id="item-type"),
        pytest.param([1, 2], [1], at(list), id="length"),
        pytest.param({"a": [1]}, {"a": [2]}, at(int, "a", 0), id="nested-value"),
        pytest.param({"a": 1}, {"b": 1}, at(dict), id="key"),
        pytest.param({"a": 1}, {"a": 1, "b": 2}, at(dict), id="key-count"),
        pytest.param({1: "a"}, {True: "a"}, at(dict), id="key-type"),
        pytest.param({2: (1,)}, {2: [1]}, at(tuple, 2), id="integer-key"),
        pytest.param({(1,): (1,)}, {(1,): [1]}, at(tuple), id="key-with-no-place"),
        pytest.param(
            Line.model_construct(price=True), Line(price=1), at(bool, "price"), id="model-field"
        ),
        pytest.param({frozenset({True})}, {frozenset({1})}, at(bool), id="set-member-type"),
        pytest.param({1}, {1, 2}, at(set), id="set-size"),
        pytest.param({1}, {2}, at(int), id="set-member"),
    ],
)
def test_it_finds_the_first_part_that_differs(
    value: object, read: object, expected: tuple[type, list[str | int]]
) -> None:
    assert difference(value, read) == expected


def test_a_datetime_subclass_may_come_back_as_a_datetime() -> None:
    at = datetime(2026, 1, 1, tzinfo=UTC)

    assert difference(DatePoint(2026, 1, 1, tzinfo=UTC), at) == (None, [])


@pytest.mark.parametrize(
    ("value", "read", "expected"),
    [
        pytest.param(Levelled(Level.LOW), Levelled(1), at(Level, "x"), id="named-tuple"),
        pytest.param(Numbered(True), Numbered(1), at(bool, "x"), id="named-tuple-bool"),
        pytest.param(deque([Level.LOW]), deque([1]), at(Level, 0), id="deque"),
        pytest.param(deque([1, 2]), deque([1]), at(deque), id="deque-length"),
        pytest.param(
            OrderedDict({"a": Level.LOW}), OrderedDict({"a": 1}), at(Level, "a"), id="ordered-dict"
        ),
        pytest.param(
            OrderedDict({"a": 1, "b": 2}),
            OrderedDict({"b": 2, "a": 1}),
            at(OrderedDict),
            id="ordered-dict-order",
        ),
        pytest.param(
            defaultdict(int, a=Level.LOW), defaultdict(int, a=1), at(Level, "a"), id="defaultdict"
        ),
        pytest.param(Counter({"a": True}), Counter({"a": 1}), at(bool, "a"), id="counter"),
        pytest.param(Counter({Level.LOW: 1}), Counter({1: 1}), at(Counter), id="counter-key"),
        pytest.param(Rows([True]), Rows([1]), at(bool, 0), id="list-subclass"),
        pytest.param(Members({True}), Members({1}), at(bool), id="set-subclass"),
        pytest.param([Identical([1])], [Identical([1])], at(Identical, 0), id="own-equality"),
    ],
)
def test_a_container_of_a_subclass_is_looked_into_as_its_base_is(
    value: object, read: object, expected: tuple[type, list[str | int]]
) -> None:
    assert difference(value, read) == expected


def test_equal_containers_of_a_subclass_have_no_difference() -> None:
    def build() -> list[object]:
        return [Levelled(1), deque([1]), OrderedDict({"a": 1}), Counter({"a": 1}), Rows([1])]

    assert difference(build(), build()) == (None, [])


class Fussy(BaseModel):
    """A model whose equality of its own no copy satisfies."""

    price: int

    @override
    def __eq__(self, other: object) -> bool:
        return other is self

    @override
    def __hash__(self) -> int:
        return id(self)


@pytest.mark.parametrize(
    ("value", "read"),
    [(Ledger(1), Ledger(1)), (Fussy(price=1), Fussy(price=1))],
    ids=["dataclass-without-equality", "model"],
)
def test_an_object_with_an_equality_of_its_own_is_compared_by_it_where_it_sits(
    value: object, read: object
) -> None:
    assert difference([value], [read]) == (type(value), [0])


@pytest.mark.parametrize("build", GENERATED_EQUALITIES.values(), ids=GENERATED_EQUALITIES.keys())
def test_a_dataclass_comparing_by_its_generated_equality_is_looked_into(
    build: Callable[[int], object],
) -> None:
    assert difference([build(1)], [build(2)]) == (int, [0, "count"])


@pytest.mark.parametrize(
    "build", HAND_WRITTEN_EQUALITIES.values(), ids=HAND_WRITTEN_EQUALITIES.keys()
)
def test_a_dataclass_with_an_equality_written_by_hand_is_compared_by_it(
    build: Callable[[int | None], object],
) -> None:
    value = build(None)

    assert difference([value], [build(None)]) == (type(value), [0])


class Sealed(BaseModel):
    """A model holding a private attribute, which pydantic's equality compares."""

    price: int
    _seal: int = PrivateAttr(default=0)


def test_the_private_attributes_of_a_model_are_compared_where_it_sits() -> None:
    sealed = Sealed(price=1)
    sealed._seal = 1

    assert difference({"a": sealed}, {"a": Sealed(price=1)}) == (Sealed, ["a"])


class Priced(BaseModel):
    """A model caching what it computes from its fields beside them."""

    price: int

    @cached_property
    def doubled(self) -> int:
        return self.price * 2


class PricedParcel(ExtendedParcel):
    """A dataclass keeping extra fields, caching what it computes beside its fields."""

    @cached_property
    def doubled(self) -> int:
        return self.weight * 2


@pytest.mark.parametrize(
    ("value", "read"),
    [(Priced(price=1), Priced(price=1)), (PricedParcel(weight=1), PricedParcel(weight=1))],
    ids=["model", "dataclass-keeping-extra-fields"],
)
def test_what_an_object_caches_beside_its_fields_is_not_compared(
    value: Priced | PricedParcel, read: object
) -> None:
    _ = value.doubled

    assert difference(value, read) == (None, [])


@pytest.mark.parametrize(
    ("value", "read", "expected"),
    [
        pytest.param(
            Extended.model_validate({"price": 1, "level": Level.LOW}),
            Extended.model_validate({"price": 1, "level": 1}),
            at(Level, "level"),
            id="model-extra-type",
        ),
        pytest.param(
            Extended(price=1),
            Extended.model_validate({"price": 1, "note": "a"}),
            at(Extended),
            id="model-extra-only-in-the-copy",
        ),
        pytest.param(
            TypeAdapter(ExtendedParcel).validate_python({"weight": 1, "note": "a"}),
            ExtendedParcel(weight=1),
            at(str, "note"),
            id="dataclass-extra-not-in-the-copy",
        ),
    ],
)
def test_the_extra_fields_of_an_object_are_compared_by_exact_type(
    value: object, read: object, expected: tuple[type, list[str | int]]
) -> None:
    assert difference(value, read) == expected


def test_extra_fields_read_back_alike_have_no_difference() -> None:
    data = {"price": 1, "note": "a"}

    assert difference(Extended.model_validate(data), Extended.model_validate(data)) == (None, [])


def test_an_extra_field_named_as_a_method_of_its_class_is_compared() -> None:
    parcels = TypeAdapter(LabelledParcel)
    value = parcels.validate_python({"weight": 1, "label": Level.LOW})
    read = parcels.validate_python({"weight": 1, "label": 1})

    assert difference(value, read) == at(Level, "label")


def test_a_comparison_that_raises_leaves_the_steps_where_it_raised() -> None:
    steps: list[str | int] = []

    with pytest.raises(InvalidOperation):
        _ = first_difference(
            {"a": [Decimal("sNaN")]}, {"a": [Decimal("sNaN")]}, steps, by_alias=True
        )

    assert steps == ["a", 0]


@pytest.mark.parametrize(("by_alias", "step"), [(True, "itemCount"), (False, "item_count")])
def test_a_field_is_named_as_it_is_written(by_alias: bool, step: str) -> None:
    steps: list[str | int] = []

    found = first_difference(
        Tally.model_construct(item_count=True), Tally(itemCount=1), steps, by_alias=by_alias
    )

    assert (found, steps) == (bool, [step])


def nested(depth: int) -> object:
    value: object = 0
    for _ in range(depth):
        value = [value]
    return value


@dataclass
class Link:
    """A link of a chain, holding the next one."""

    next: Link | None


class ModelLink(BaseModel):
    """A link of a chain of models, holding the next one."""

    next: ModelLink | None


def links(depth: int) -> Link | None:
    link: Link | None = None
    for _ in range(depth):
        link = Link(link)
    return link


def model_links(depth: int) -> ModelLink | None:
    link: ModelLink | None = None
    for _ in range(depth):
        link = ModelLink(next=link)
    return link


class Rooted(RootModel[list[object]]):
    """A model holding a list as a whole, which may hold another."""


def rooted(depth: int) -> Rooted:
    root = Rooted([])
    for _ in range(depth):
        root = Rooted([root])
    return root


@pytest.mark.parametrize(
    "build",
    [lambda: nested(300), lambda: links(150), lambda: model_links(150), lambda: rooted(150)],
    ids=["lists", "dataclasses", "models", "root-models"],
)
def test_a_deep_value_is_compared_however_little_of_the_stack_is_left(
    build: Callable[[], object],
) -> None:
    value, read = build(), build()

    def compare_from(depth: int) -> type | None:
        if depth:
            return compare_from(depth - 1)
        return first_difference(value, read, [], by_alias=True)

    # Leaves a few dozen frames of the stack for the comparison, far fewer than the value's depth.
    assert compare_from(sys.getrecursionlimit() - len(inspect.stack(0)) - 50) is None
