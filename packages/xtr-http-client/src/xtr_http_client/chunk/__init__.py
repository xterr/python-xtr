"""The five kinds of piece a transfer arrives in.

A response stream hands over one of these at a time, and which class it is
answers what just happened: :class:`DataChunk` for bytes of the body,
:class:`FirstChunk` for the head having arrived, :class:`LastChunk` for the
body being complete, :class:`InformationalChunk` for a 1xx status ahead of the
real one, and :class:`ErrorChunk` for a transfer that went quiet or failed.

Every one of them satisfies :class:`ChunkInterface
<xtr_http_client_contracts.chunk_interface.ChunkInterface>`, so a reader asks
the same four questions whichever arrived.
"""

from __future__ import annotations

from .data_chunk import DataChunk
from .error_chunk import ErrorChunk
from .first_chunk import FirstChunk
from .informational_chunk import InformationalChunk
from .last_chunk import LastChunk

__all__ = [
    "DataChunk",
    "ErrorChunk",
    "FirstChunk",
    "InformationalChunk",
    "LastChunk",
]
