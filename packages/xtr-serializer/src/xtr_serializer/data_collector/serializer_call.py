"""One call made on a traced serializer, as the profiler keeps it."""

from __future__ import annotations

from typing import TypedDict

__all__ = ["SerializerCall"]


class SerializerCall(TypedDict):
    """What a profile keeps of one call: plain data, so it is written as it is recorded.

    Nothing the call was handed is kept — not the value, not the text, not a context value —
    only what names it, so a profile never holds a credential the data carried.

    Attributes:
        serializer: The name of the serializer called, ``"default"`` for the unnamed one.
        method: ``serialize``, ``deserialize``, ``normalize``, ``denormalize``, ``encode`` or
            ``decode``.
        data_type: The qualified name of the class of the value handed in.
        target_type: The type asked for, as written, for ``deserialize`` and ``denormalize``;
            ``None`` for every other method.
        format: The format named, or ``None`` when the call named none.
        context: The keys of the context the call passed, in order; empty without one.
        duration_ms: How long the call took, in milliseconds.
        error: The ``class`` and ``message`` of what it raised, or ``None`` when it returned.
    """

    serializer: str
    method: str
    data_type: str
    target_type: str | None
    format: str | None
    context: list[str]
    duration_ms: float
    error: dict[str, str] | None
