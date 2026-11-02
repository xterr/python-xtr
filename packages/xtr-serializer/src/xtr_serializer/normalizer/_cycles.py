"""pydantic's refusal of a value that contains itself, told apart from its other refusals."""

from __future__ import annotations

from typing import Final

__all__ = ["is_cycle"]

# pydantic's words for a value that contains itself: a plain ValueError when dumping, wrapped
# when writing JSON. Its "(depth exceeded)" is a value nested too deep, which is no cycle.
_CYCLE: Final = "Circular reference detected (id repeated)"
_CYCLE_WORDS: Final = frozenset({_CYCLE, f"Error serializing to JSON: ValueError: {_CYCLE}"})


def is_cycle(error: ValueError) -> bool:
    """Tell pydantic's refusal of a value that contains itself, which has no type of its own."""
    return str(error) in _CYCLE_WORDS
