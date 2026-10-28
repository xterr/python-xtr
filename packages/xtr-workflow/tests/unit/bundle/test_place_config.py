"""A place's configuration is its name and its metadata."""

from __future__ import annotations

from xtr_workflow.bundle import PlaceConfig


def test_a_place_has_no_metadata_by_default() -> None:
    place = PlaceConfig("draft")

    assert place.name == "draft"
    assert place.metadata == {}


def test_a_place_keyed_by_its_name_needs_no_name_of_its_own() -> None:
    assert PlaceConfig(metadata={"color": "blue"}).name == ""
