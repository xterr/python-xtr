"""A transition marker keeps its description in its metadata, where the dumpers read it."""

from __future__ import annotations

import pytest

from xtr_workflow import Arc
from xtr_workflow.decorator import Transition
from xtr_workflow.exception import LogicError


def test_the_description_is_stored_in_the_metadata() -> None:
    marker = Transition(
        "draft",
        "published",
        description="Makes the article public",
        metadata={"label": "Publish"},
    )

    assert marker.metadata == {"label": "Publish", "description": "Makes the article public"}


def test_without_a_description_the_metadata_is_kept_as_given() -> None:
    marker = Transition("draft", "published", metadata={"label": "Publish"})

    assert marker.metadata == {"label": "Publish"}


def test_the_description_is_the_third_argument() -> None:
    marker = Transition("draft", "published", "Makes the article public")

    assert marker.metadata == {"description": "Makes the article public"}
    assert marker.guard is None


def test_the_places_are_kept_as_given() -> None:
    arcs = [Arc("a", 2), "b"]

    marker = Transition(arcs, "c")

    assert marker.froms is arcs
    assert marker.tos == "c"


def test_the_description_and_a_description_in_the_metadata_cannot_be_used_together() -> None:
    with pytest.raises(LogicError) as raised:
        _ = Transition(
            "draft",
            "published",
            description="Makes the article public",
            metadata={"description": "Publishes the article"},
        )

    assert str(raised.value) == (
        'The "description" argument of "Transition" cannot be used together with a "description" '
        'key in its "metadata" argument.'
    )
