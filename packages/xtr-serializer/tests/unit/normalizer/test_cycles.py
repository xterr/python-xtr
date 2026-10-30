"""pydantic's refusal of a value that contains itself, told apart from its other refusals."""

from __future__ import annotations

import pytest

from xtr_serializer.normalizer._cycles import is_cycle


@pytest.mark.parametrize(
    "words",
    [
        "Circular reference detected (id repeated)",
        "Error serializing to JSON: ValueError: Circular reference detected (id repeated)",
    ],
    ids=["dumping", "writing-json"],
)
def test_it_tells_a_cycle(words: str) -> None:
    assert is_cycle(ValueError(words))


def test_a_value_nested_too_deep_is_no_cycle() -> None:
    assert not is_cycle(ValueError("Circular reference detected (depth exceeded)"))
