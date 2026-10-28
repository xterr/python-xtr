"""A subject whose setter is annotated with names only the type checker imports."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import Mapping

    from tests.fixtures.place_enum import PlaceEnum


@final
class SubjectWithUnreadableAnnotation:
    def __init__(self) -> None:
        self._marking: PlaceEnum | Mapping[str, int] | None = None

    def get_marking(self) -> PlaceEnum | Mapping[str, int] | None:
        return self._marking

    def set_marking(self, marking: PlaceEnum | Mapping[str, int]) -> None:
        self._marking = marking
