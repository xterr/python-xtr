"""A definition validator that only records what it was called with."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

if TYPE_CHECKING:
    from xtr_workflow import Definition


@final
class DefinitionValidator:
    calls: ClassVar[list[tuple[Definition, str]]] = []

    def validate(self, definition: Definition, name: str) -> None:
        DefinitionValidator.calls.append((definition, name))
