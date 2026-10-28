"""An arc's configuration names its place, however given, and weighs it at least 1."""

from __future__ import annotations

import pytest

from tests.fixtures.task_step import TaskStep
from xtr_workflow.bundle import ArcConfig
from xtr_workflow.exception import InvalidArgumentError


def test_an_arc_weighs_one_by_default() -> None:
    assert ArcConfig("draft").weight == 1


def test_an_enum_member_names_the_place_by_its_value() -> None:
    assert ArcConfig(TaskStep.PROCESSING, 2) == ArcConfig("processing", 2)


def test_a_weight_below_one_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = ArcConfig("draft", 0)

    assert str(raised.value) == (
        "The value 0 is too small for the weight of an arc. Should be greater than or equal to 1."
    )


def test_an_empty_place_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = ArcConfig("")

    assert str(raised.value) == 'The place of an arc cannot contain an empty value, but got "".'
