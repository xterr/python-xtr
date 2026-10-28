"""What the Graphviz dumpers gather about a definition before writing it."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TypeAlias

__all__ = ["Edge", "Listeners", "PlaceEdge", "PlaceNode", "TransitionNode"]

Listeners: TypeAlias = Mapping[str, Mapping[str, Sequence[Mapping[str, object]]]]
"""The listeners of each transition, under ``"transition__<number>"``, by event."""


@dataclass(frozen=True, slots=True)
class PlaceNode:
    """A place as drawn: its node attributes, the metadata it lists, the label naming it."""

    attributes: dict[str, object]
    metadata: dict[str, object]
    label: object | None


@dataclass(frozen=True, slots=True)
class TransitionNode:
    """A transition as drawn: its node attributes, the name it shows, the metadata it lists."""

    attributes: dict[str, object]
    name: object
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class Edge:
    """An arc as drawn, between a place and the box of transition number ``transition_number``."""

    place: str
    transition_number: int
    leaves_place: bool
    weight: int


@dataclass(frozen=True, slots=True)
class PlaceEdge:
    """A transition as drawn from one place: the name it shows, the place it enters, its style."""

    name: object
    to: str
    attributes: Mapping[str, object]
