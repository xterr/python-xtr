"""Configuration of one place of a configured workflow."""

from __future__ import annotations

# Read at runtime: the dataclass below resolves its annotations from this module.
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import final

__all__ = ["PlaceConfig"]


@final
@dataclass(frozen=True, slots=True)
class PlaceConfig:
    """A place of a configured workflow, and what it says about it.

    A workflow lists a place to add one no transition uses, to fix the order
    of its places, or to give it metadata; a place a transition uses needs no
    configuration of its own.

    Attributes:
        name: The name of the place. A place keyed by its name in
            :attr:`WorkflowDefinitionConfig.places` may leave it empty, to be
            named by its key.
        metadata: The metadata of the place, its ``description`` included.
    """

    name: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict[str, object])
