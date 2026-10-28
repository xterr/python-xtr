"""Subjects keeping their place as a member of an enum, behind accessors or in an attribute."""

from __future__ import annotations

# ``typing`` itself, not only names from it: an annotation below reads it.
import typing
from typing import final

from tests.fixtures.place_enum import PlaceEnum

if typing.TYPE_CHECKING:
    from collections.abc import Mapping


@final
class SubjectWithEnum:
    def __init__(self, marking: PlaceEnum | None = None) -> None:
        self._marking = marking
        self._context: dict[str, object] = {}

    def get_marking(self) -> PlaceEnum | None:
        return self._marking

    def set_marking(self, marking: PlaceEnum, context: Mapping[str, object] | None = None) -> None:
        self._marking = marking
        self._context = dict(context) if context is not None else {}

    def get_context(self) -> dict[str, object]:
        return self._context


@final
class AsyncSubjectWithEnum:
    def __init__(self, marking: PlaceEnum | None = None) -> None:
        self._marking = marking
        self._context: dict[str, object] = {}

    async def get_marking(self) -> PlaceEnum | None:
        return self._marking

    async def set_marking(
        self, marking: PlaceEnum, context: Mapping[str, object] | None = None
    ) -> None:
        self._marking = marking
        self._context = dict(context) if context is not None else {}

    def get_context(self) -> dict[str, object]:
        return self._context


@final
class SubjectWithEnumAttribute:
    marking: PlaceEnum | None = None


@final
class SubjectWithOptionalEnumAttribute:
    marking: PlaceEnum | None = None


# The ``Optional[...]`` spelling, which has an origin of its own before 3.14;
# written as a string so that nothing else here has to use it.
SubjectWithOptionalEnumAttribute.__annotations__["marking"] = "typing.Optional[PlaceEnum]"
