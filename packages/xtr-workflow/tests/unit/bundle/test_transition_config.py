"""A transition's configuration reads its arcs from every shorthand, and checks its weight."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from tests.fixtures.task_step import TaskStep
from xtr_workflow import Arc
from xtr_workflow.bundle import ArcConfig, TransitionConfig
from xtr_workflow.exception import InvalidArgumentError

if TYPE_CHECKING:
    from xtr_workflow.event_listener import GuardContext


def _always(_context: GuardContext) -> bool:
    return True


def test_a_single_place_name_is_one_arc() -> None:
    transition = TransitionConfig("publish", "draft", "published")

    assert transition.froms == (ArcConfig("draft"),)
    assert transition.tos == (ArcConfig("published"),)


def test_a_single_enum_member_is_one_arc_to_its_value() -> None:
    transition = TransitionConfig("start", TaskStep.NEW, TaskStep.PROCESSING)

    assert transition.froms == (ArcConfig("new"),)
    assert transition.tos == (ArcConfig("processing"),)


def test_a_single_arc_keeps_its_weight() -> None:
    transition = TransitionConfig("merge", Arc("done", 2), ArcConfig(TaskStep.DONE, 3))

    assert transition.froms == (ArcConfig("done", 2),)
    assert transition.tos == (ArcConfig("done", 3),)


def test_a_sequence_mixes_every_way_of_naming_a_place() -> None:
    transition = TransitionConfig(
        "merge", ["draft", TaskStep.NEW, Arc("done", 2), ArcConfig("failed", 3)], ("archived",)
    )

    assert transition.froms == (
        ArcConfig("draft"),
        ArcConfig("new"),
        ArcConfig("done", 2),
        ArcConfig("failed", 3),
    )
    assert transition.tos == (ArcConfig("archived"),)


def test_an_arc_that_names_no_place_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = TransitionConfig("publish", [cast("str", cast("object", 1))], "published")

    assert str(raised.value) == (
        'The "froms" arcs must be a list of strings, enum members, arcs or arc configurations in '
        "workflow configuration."
    )


def test_the_arcs_of_tos_are_checked_too() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = TransitionConfig("publish", "draft", [cast("str", cast("object", None))])

    assert str(raised.value).startswith('The "tos" arcs must be a list of strings')


def test_a_transition_has_no_guard_no_metadata_and_a_weight_of_one_by_default() -> None:
    transition = TransitionConfig("publish", "draft", "published")

    assert transition.guard is None
    assert transition.metadata == {}
    assert transition.weight == 1


def test_the_guard_and_metadata_are_kept() -> None:
    transition = TransitionConfig(
        "publish", "draft", "published", guard=_always, metadata={"color": "blue"}
    )

    assert transition.guard is _always
    assert transition.metadata == {"color": "blue"}


def test_the_transition_weight_is_kept_without_weighing_its_arcs() -> None:
    transition = TransitionConfig("publish", "draft", "published", weight=3)

    assert transition.weight == 3
    assert transition.froms == (ArcConfig("draft", 1),)
    assert transition.tos == (ArcConfig("published", 1),)


def test_a_transition_weight_below_one_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = TransitionConfig("publish", "draft", "published", weight=0)

    assert str(raised.value) == "The weight must be greater than 0."
