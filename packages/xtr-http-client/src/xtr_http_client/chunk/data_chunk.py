"""A piece of a body, with no event to report."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = ["DataChunk"]


class DataChunk:
    """Bytes that arrived, and where in the body they belong.

    The plain chunk of the five, and the base the other four narrow: each of
    them *is* a piece of the transfer that happens to also report an event, so
    they answer everything here and override only the one question that is
    theirs.

    It is built with no arguments too, for a chunk that marks a point in the
    transfer rather than carrying bytes — the head having arrived, or a 1xx
    coming in ahead of the real status.
    """

    __slots__: tuple[str, ...] = ("_content", "_offset")

    _offset: int
    _content: bytes

    def __init__(self, offset: int = 0, content: bytes = b"") -> None:
        """Record where in the body this chunk sits, and what it carries."""
        self._offset = offset
        self._content = content

    def is_timeout(self) -> bool:
        """Say that the transfer is going along; only an error chunk reports a timeout."""
        return False

    def is_first(self) -> bool:
        """Say that this is not the head of the response."""
        return False

    def is_last(self) -> bool:
        """Say that the body is not complete."""
        return False

    def get_informational_status(self) -> tuple[int, Mapping[str, Sequence[str]]] | None:
        """Say that no 1xx status came in with this chunk."""
        return None

    def get_content(self) -> bytes:
        """Return the piece of the body this chunk carries."""
        return self._content

    def get_offset(self) -> int:
        """Return where this chunk's content sits in the body."""
        return self._offset

    def get_error(self) -> str | None:
        """Say that nothing has gone wrong with the transfer."""
        return None
