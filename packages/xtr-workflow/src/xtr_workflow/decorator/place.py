"""Marking a place of a workflow declared on a class."""

from __future__ import annotations

# Read at runtime: the dataclass below resolves its annotations from this module.
from collections.abc import Mapping
from dataclasses import InitVar, dataclass, field
from typing import final

from ._build_metadata import build_metadata

__all__ = ["Place"]


@final
@dataclass(frozen=True, slots=True)
class Place:
    """A place of a workflow declared with ``@as_workflow``, with what it says about it.

    Put it on a class constant valued with the place's name, to add a place
    no transition uses or to describe one:
    ``REVIEW: ClassVar[Annotated[str, Place(initial=True)]] = "review"``. For
    the members of an enum of places, hand it to ``@as_workflow`` through
    ``place_markers`` instead, keyed by the member.

    Attributes:
        metadata: The metadata of the place, its description included.
        initial: Whether the place is in the initial marking, unless the
            workflow declares its ``initial_marking``.
    """

    description: InitVar[str | None] = None
    """The description of the place, kept under the ``description`` key of its metadata."""

    metadata: Mapping[str, object] = field(default_factory=dict[str, object])
    initial: bool = False

    def __post_init__(self, description: str | None) -> None:
        """Join ``description`` to the metadata.

        Raises:
            LogicError: If the metadata has a description of its own.
        """
        object.__setattr__(self, "metadata", build_metadata(self.metadata, description, "Place"))
