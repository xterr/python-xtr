"""The body is complete."""

from __future__ import annotations

from typing import final

from typing_extensions import override

from xtr_http_client.chunk.data_chunk import DataChunk

__all__ = ["LastChunk"]


@final
class LastChunk(DataChunk):
    """The end of the transfer; nothing further arrives for this response.

    Its offset is where the body ended, so a reader that was writing pieces
    away by offset learns the total length from it without counting.
    """

    __slots__: tuple[str, ...] = ()

    @override
    def is_last(self) -> bool:
        """Say that nothing further arrives for this response."""
        return True
