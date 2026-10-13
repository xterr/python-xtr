"""A 1xx status came in ahead of the real one."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_http_client.chunk.data_chunk import DataChunk

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = ["InformationalChunk"]


@final
class InformationalChunk(DataChunk):
    """A status a server sent before settling on one, with the headers it carried.

    A 103 listing what to fetch early, a 100 agreeing to receive a body: any
    number of them may arrive before the status that counts, and none of them
    is the head of the response. So this carries no body and reports nothing
    but the status it came with, leaving :class:`FirstChunk
    <xtr_http_client.chunk.first_chunk.FirstChunk>` to mark the real head.
    """

    __slots__: tuple[str, ...] = ("_status",)

    _status: tuple[int, Mapping[str, Sequence[str]]]

    def __init__(self, status_code: int, headers: Mapping[str, Sequence[str]]) -> None:
        """Record the 1xx status and the headers that came with it."""
        super().__init__()
        self._status = (status_code, headers)

    @override
    def get_informational_status(self) -> tuple[int, Mapping[str, Sequence[str]]] | None:
        """Return the 1xx status that came in, with the headers it carried."""
        return self._status
