"""Handlers that wrap other handlers, as configuration.

A wrapper names what it wraps — ``handler: file_log``, or ``members: [a, b]``
— and a handler named that way leaves every channel's stack: it only
receives what its wrapper passes it.
"""

from __future__ import annotations

from typing_extensions import override

from xtr_logging.level import Level

from .handler_specs import BaseHandlerSpec

__all__ = [
    "BufferHandlerSpec",
    "DeduplicationHandlerSpec",
    "FallbackGroupHandlerSpec",
    "FilterHandlerSpec",
    "FingersCrossedHandlerSpec",
    "GroupHandlerSpec",
    "QueueHandlerSpec",
    "SamplingHandlerSpec",
    "WhatFailureGroupHandlerSpec",
]


class _WrappingHandlerSpec(BaseHandlerSpec, frozen=True, kw_only=True):
    handler: str

    @property
    @override
    def references(self) -> tuple[str, ...]:
        return (self.handler,)


class _GroupingHandlerSpec(BaseHandlerSpec, frozen=True, kw_only=True):
    members: tuple[str, ...]

    @property
    @override
    def references(self) -> tuple[str, ...]:
        return self.members


class FingersCrossedHandlerSpec(
    _WrappingHandlerSpec, frozen=True, kw_only=True, tag="fingers_crossed"
):
    """A :class:`~xtr_logging.handler.fingers_crossed_handler.FingersCrossedHandler`.

    Buffers every record and writes them all to ``handler`` once one reaches
    ``action_level`` — or the level ``channel_levels`` sets for its channel.
    ``activation_strategy`` names a supplied strategy service instead.
    """

    action_level: Level | str = Level.WARNING
    channel_levels: dict[str, Level | str] | None = None
    activation_strategy: str | None = None
    buffer_size: int = 0
    stop_buffering: bool = True
    passthru_level: Level | str | None = None

    @override
    def __post_init__(self) -> None:
        super().__post_init__()
        _ = Level.parse(self.action_level)
        for level in (self.channel_levels or {}).values():
            _ = Level.parse(level)
        if self.passthru_level is not None:
            _ = Level.parse(self.passthru_level)


class BufferHandlerSpec(_WrappingHandlerSpec, frozen=True, kw_only=True, tag="buffer"):
    """A :class:`~xtr_logging.handler.buffer_handler.BufferHandler`."""

    level: Level | str = Level.DEBUG
    buffer_size: int = 0
    flush_on_overflow: bool = False

    @override
    def __post_init__(self) -> None:
        super().__post_init__()
        _ = Level.parse(self.level)


class FilterHandlerSpec(_WrappingHandlerSpec, frozen=True, kw_only=True, tag="filter"):
    """A :class:`~xtr_logging.handler.filter_handler.FilterHandler`.

    Passes ``accepted_levels`` when given, otherwise the range from
    ``min_level`` to ``max_level``.
    """

    accepted_levels: tuple[Level | str, ...] | None = None
    min_level: Level | str = Level.DEBUG
    max_level: Level | str = Level.EMERGENCY

    @override
    def __post_init__(self) -> None:
        super().__post_init__()
        for level in (*(self.accepted_levels or ()), self.min_level, self.max_level):
            _ = Level.parse(level)


class DeduplicationHandlerSpec(
    _WrappingHandlerSpec, frozen=True, kw_only=True, tag="deduplication"
):
    """A :class:`~xtr_logging.handler.deduplication_handler.DeduplicationHandler`."""

    store: str | None = None
    deduplication_level: Level | str = Level.ERROR
    time: int = 60

    @override
    def __post_init__(self) -> None:
        super().__post_init__()
        _ = Level.parse(self.deduplication_level)


class SamplingHandlerSpec(_WrappingHandlerSpec, frozen=True, kw_only=True, tag="sampling"):
    """A :class:`~xtr_logging.handler.sampling_handler.SamplingHandler`.

    Passes one record in ``factor``.
    """

    factor: int


class QueueHandlerSpec(_WrappingHandlerSpec, frozen=True, kw_only=True, tag="queue"):
    """A :class:`~xtr_logging.handler.queue_handler.QueueHandler`.

    Hands records to a background thread, so logging never waits on I/O.
    """

    max_size: int = 0


class GroupHandlerSpec(_GroupingHandlerSpec, frozen=True, kw_only=True, tag="group"):
    """A :class:`~xtr_logging.handler.group_handler.GroupHandler`.

    Every member gets every record.
    """


class WhatFailureGroupHandlerSpec(
    _GroupingHandlerSpec, frozen=True, kw_only=True, tag="whatfailuregroup"
):
    """A :class:`~xtr_logging.handler.what_failure_group_handler.WhatFailureGroupHandler`.

    Like ``group``, but a failing member never stops the others.
    """


class FallbackGroupHandlerSpec(
    _GroupingHandlerSpec, frozen=True, kw_only=True, tag="fallbackgroup"
):
    """A :class:`~xtr_logging.handler.fallback_group_handler.FallbackGroupHandler`.

    Members are tried in order until one succeeds.
    """
