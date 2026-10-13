"""The status line and the headers have arrived."""

from __future__ import annotations

from typing import final

from typing_extensions import override

from xtr_http_client.chunk.data_chunk import DataChunk

__all__ = ["FirstChunk"]


@final
class FirstChunk(DataChunk):
    """The head of the response, which is the point the status can be read from.

    Yielded once per head, so a redirect that was followed yields one for each
    hop. It may carry the first bytes of the body along with it, which is why
    it is a data chunk rather than a marker of its own.
    """

    __slots__: tuple[str, ...] = ()

    @override
    def is_first(self) -> bool:
        """Say that the status and the headers can be read from here on."""
        return True
