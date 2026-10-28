"""A description joins the metadata under the key the dumpers read, never over one given there."""

from __future__ import annotations

import pytest

from xtr_workflow.decorator._build_metadata import build_metadata
from xtr_workflow.exception import LogicError


def test_without_a_description_the_metadata_is_copied() -> None:
    metadata = {"title": "Articles"}

    built = build_metadata(metadata, None, "Place")

    assert built == {"title": "Articles"}
    assert built is not metadata


def test_a_description_is_added_under_the_description_key() -> None:
    assert build_metadata({"title": "Articles"}, "Manages the articles", "Place") == {
        "title": "Articles",
        "description": "Manages the articles",
    }


def test_a_description_already_in_the_metadata_is_refused_naming_the_declaration() -> None:
    with pytest.raises(LogicError) as raised:
        _ = build_metadata({"description": "x"}, "y", "Declared")

    assert str(raised.value) == (
        'The "description" argument of "Declared" cannot be used together with a "description" '
        'key in its "metadata" argument.'
    )
