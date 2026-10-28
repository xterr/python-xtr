"""A place marker keeps its description in its metadata, where the dumpers read it."""

from __future__ import annotations

import pytest

from xtr_workflow.decorator import Place
from xtr_workflow.exception import LogicError


def test_the_description_is_stored_in_the_metadata() -> None:
    marker = Place("Waiting for a review", {"label": "Draft"})

    assert marker.metadata == {"label": "Draft", "description": "Waiting for a review"}


def test_without_a_description_the_metadata_is_kept_as_given() -> None:
    assert Place(metadata={"label": "Draft"}).metadata == {"label": "Draft"}


def test_a_place_is_not_initial_unless_told() -> None:
    assert not Place().initial
    assert Place(initial=True).initial


def test_the_description_and_a_description_in_the_metadata_cannot_be_used_together() -> None:
    with pytest.raises(LogicError) as raised:
        _ = Place("Waiting for a review", {"description": "Waiting for a reviewer"})

    assert str(raised.value) == (
        'The "description" argument of "Place" cannot be used together with a "description" '
        'key in its "metadata" argument.'
    )
