"""Subjects keeping their marking, and the context it was last set with, behind accessors.

``Subject``'s accessors are plain methods; ``AsyncSubject``'s are coroutines,
as a subject persisting its own state has.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    # Only the type checker reads the context's annotation: a store reads no
    # more of a setter than its first parameter.
    from collections.abc import Mapping


@final
class Subject:
    def __init__(self, marking: object = None) -> None:
        self._marking = marking
        self._context: dict[str, object] = {}

    def get_marking(self) -> object:
        return self._marking

    def set_marking(self, marking: object, context: Mapping[str, object] | None = None) -> None:
        self._marking = marking
        self._context = dict(context) if context is not None else {}

    def get_context(self) -> dict[str, object]:
        return self._context


@final
class AsyncSubject:
    def __init__(self, marking: object = None) -> None:
        self._marking = marking
        self._context: dict[str, object] = {}

    async def get_marking(self) -> object:
        return self._marking

    async def set_marking(
        self, marking: object, context: Mapping[str, object] | None = None
    ) -> None:
        self._marking = marking
        self._context = dict(context) if context is not None else {}

    def get_context(self) -> dict[str, object]:
        return self._context
