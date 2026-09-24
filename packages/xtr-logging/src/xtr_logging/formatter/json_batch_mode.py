"""How several records become JSON together: one array, or one object per line."""

from __future__ import annotations

from enum import IntEnum

__all__ = ["JsonBatchMode"]


class JsonBatchMode(IntEnum):
    """How ``JsonFormatter.format_batch`` renders several records together.

    ``JSON`` renders the batch as a single JSON array, which a reader parses in
    one call. ``NEWLINES`` renders one JSON object per line — the
    newline-delimited JSON that log shippers and ``jq`` expect.
    """

    JSON = 1
    NEWLINES = 2
