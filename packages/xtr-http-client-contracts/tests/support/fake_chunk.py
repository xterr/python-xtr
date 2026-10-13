"""One piece of a streamed body, as the contract describes a chunk."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = ["FakeChunk"]


@final
@dataclass(frozen=True, slots=True)
class FakeChunk:
    """A chunk whose answers are the fields it was built with.

    A value object rather than a pile of constructor arguments, so a test
    names only the one fact it cares about: ``FakeChunk(first=True)`` is the
    headers having arrived, ``FakeChunk(b"body", offset=12)`` a piece of the
    body.
    """

    content: bytes = b""
    offset: int = 0
    first: bool = False
    last: bool = False
    timeout: bool = False
    informational: tuple[int, Mapping[str, Sequence[str]]] | None = None
    error: str | None = None

    def is_timeout(self) -> bool:
        return self.timeout

    def is_first(self) -> bool:
        return self.first

    def is_last(self) -> bool:
        return self.last

    def get_informational_status(self) -> tuple[int, Mapping[str, Sequence[str]]] | None:
        return self.informational

    def get_content(self) -> bytes:
        return self.content

    def get_offset(self) -> int:
        return self.offset

    def get_error(self) -> str | None:
        return self.error
