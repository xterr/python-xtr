"""A type expression named as written, without running the code of its classes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal

import pytest

from tests.fixtures.nameless import NamelessThing, names_refused
from tests.fixtures.refused_types import Sealed, Unprintable, nested
from xtr_serializer._written_types import written_name_of


@pytest.mark.parametrize(
    ("type_", "name"),
    [
        (list[NamelessThing], "list[NamelessThing]"),
        (dict[str, NamelessThing], "dict[str, NamelessThing]"),
        (Literal["a"] | NamelessThing, "Literal['a'] | NamelessThing"),
        (NamelessThing | None, "NamelessThing | None"),
        (Annotated[NamelessThing, "x"], "Annotated[NamelessThing, 'x']"),
        (Literal["a", 1], "Literal['a', 1]"),
        (tuple[NamelessThing, ...], "tuple[NamelessThing, ...]"),
        (Callable[[NamelessThing], None], "Callable[[NamelessThing], None]"),
    ],
    ids=["list", "dict", "typing-union", "union", "annotated", "literal", "tuple", "callable"],
)
def test_it_names_a_type_expression_without_running_a_metaclass(type_: object, name: str) -> None:
    with names_refused():
        assert written_name_of(type_) == name


@pytest.mark.parametrize(
    ("type_", "name"),
    [(Sealed, "Sealed"), (list[Sealed], "list[Sealed]")],
    ids=["alone", "in-an-expression"],
)
def test_it_names_a_class_none_of_whose_attributes_can_be_read(type_: object, name: str) -> None:
    assert written_name_of(type_) == name


@pytest.mark.parametrize(
    "type_of", [Unprintable, lambda: nested(5000)], ids=["raising-repr", "deeper-than-the-stack"]
)
def test_a_type_that_cannot_be_named_is_named_by_a_fixed_name(
    type_of: Callable[[], object],
) -> None:
    assert written_name_of(type_of()) == "a type that cannot be named"
