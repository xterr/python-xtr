"""A place named in configuration by a string or by an enum member reads as a string."""

from __future__ import annotations

from enum import IntEnum

import pytest

from tests.fixtures.place_enum import PlaceEnum
from tests.fixtures.task_step import TaskStep
from xtr_workflow.bundle._place_name import place_name
from xtr_workflow.exception import InvalidArgumentError


class _Level(IntEnum):
    ONE = 1


def test_a_string_is_the_place_name() -> None:
    assert place_name("draft") == "draft"


def test_an_enum_member_names_the_place_by_its_value() -> None:
    assert place_name(PlaceEnum.FOO) == "foo"


def test_a_string_enum_member_gives_a_plain_string() -> None:
    name = place_name(TaskStep.NEW)

    assert type(name) is str
    assert name == "new"


def test_an_enum_member_not_valued_with_a_string_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = place_name(_Level.ONE)

    assert str(raised.value) == (
        f'Only string-backed enums can be used as places, "{__name__}._Level" is not.'
    )
