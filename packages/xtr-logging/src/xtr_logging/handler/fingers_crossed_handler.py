"""Keep the whole request's log, but only once something went wrong."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_logging_contracts import Level
from xtr_service_contracts import ResetInterface

from xtr_logging.log_unit import unit_state

from ._lazy_handler import LazyHandler
from ._processor_stack import ProcessorStack
from .fingers_crossed.activation_strategy_interface import ActivationStrategyInterface
from .fingers_crossed.error_level_activation_strategy import ErrorLevelActivationStrategy
from .handler_interface import HandlerInterface

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from typing import TypeAlias

    from xtr_logging_contracts import LevelLike

    from xtr_logging.log_record import LogRecord

    _HandlerFactory: TypeAlias = Callable[
        ["LogRecord | None", "FingersCrossedHandler"],
        HandlerInterface,
    ]

__all__ = ["FingersCrossedHandler"]


@final
class _FingersCrossedState:
    """One unit's buffer and buffering flag, mutated in place so a copied context sees it."""

    __slots__ = ("buffer", "buffering")

    def __init__(self) -> None:
        self.buffer: list[LogRecord] = []
        self.buffering: bool = True


@final
class FingersCrossedHandler(ProcessorStack, LazyHandler, HandlerInterface, ResetInterface):
    """Buffers every record, and forwards the lot the moment one is bad enough.

    A healthy request leaves nothing in the log; a failed one leaves its whole
    story, context and all, not just the line that failed. The activation
    strategy decides what "bad enough" means. After it fires, records pass
    straight through — unless ``stop_buffering`` is off, which starts a fresh
    buffer for whatever follows.

    ``passthru_level`` is the floor kept even when nothing triggered: on
    :meth:`close` or :meth:`reset`, records at that level or above are still
    forwarded, so a warning is not lost just because no error joined it.

    The wrapped handler may be given as a factory
    ``handler(record, self) -> HandlerInterface``, resolved and cached the
    first time it is needed — so an expensive handler is never built for a
    request that stays quiet.
    """

    def __init__(  # noqa: PLR0913, PLR0917 — every option is independent; all have defaults
        self,
        handler: HandlerInterface | _HandlerFactory,
        activation_strategy: ActivationStrategyInterface | LevelLike | None = None,
        buffer_size: int = 0,
        bubble: bool = True,
        stop_buffering: bool = True,
        passthru_level: LevelLike | None = None,
    ) -> None:
        """Wrap ``handler`` behind a buffer released by ``activation_strategy``.

        Args:
            handler: The handler flushed to, or a factory that builds it lazily.
            activation_strategy: What releases the buffer — a strategy, or a
                level for :class:`ErrorLevelActivationStrategy`. Defaults to
                activating on ``WARNING`` and above.
            buffer_size: The most records to keep before the oldest are
                dropped; ``0`` keeps everything until activation.
            bubble: Whether records still reach later handlers.
            stop_buffering: Whether to pass records straight through once
                activated, rather than buffering a fresh batch.
            passthru_level: A floor always flushed on close or reset, even with
                no activation; ``None`` flushes nothing in that case.

        Raises:
            InvalidLevelError: If a level argument names no level.
        """
        if activation_strategy is None:
            activation_strategy = ErrorLevelActivationStrategy(Level.WARNING)
        elif not isinstance(activation_strategy, ActivationStrategyInterface):
            activation_strategy = ErrorLevelActivationStrategy(activation_strategy)
        self._wrap(handler)
        self._activation_strategy: ActivationStrategyInterface = activation_strategy
        self._buffer_size: int = buffer_size
        self._bubble: bool = bubble
        self._stop_buffering: bool = stop_buffering
        self._passthru_level: Level | None = (
            Level.parse(passthru_level) if passthru_level is not None else None
        )
        self._instance_state: _FingersCrossedState = _FingersCrossedState()
        # Swapped out under this lock before it is forwarded, so a record
        # buffered meanwhile waits for the next release rather than being lost.
        self._buffer_lock: threading.Lock = threading.Lock()

    @override
    def is_handling(self, record: LogRecord, /) -> bool:
        """Always ``True``: everything is buffered until the buffer is released."""
        return True

    @override
    def handle(self, record: LogRecord, /) -> bool:
        """Buffer ``record``, or pass it through once the buffer has been released."""
        record = self._process(record)
        state = self._state()
        if state.buffering:
            with self._buffer_lock:
                state.buffer.append(record)
                if self._buffer_size > 0 and len(state.buffer) > self._buffer_size:
                    _ = state.buffer.pop(0)
            if self._activation_strategy.is_handler_activated(record):
                self.activate()
        else:
            _ = self._resolve_handler(record).handle(record)
        return not self._bubble

    @override
    def handle_batch(self, records: Sequence[LogRecord], /) -> None:
        """Offer each record in turn, as a logger would one by one."""
        for record in records:
            _ = self.handle(record)

    def activate(self) -> None:
        """Release the buffer now, whatever the strategy would have said."""
        state = self._state()
        with self._buffer_lock:
            if self._stop_buffering:
                state.buffering = False
            pending, state.buffer = state.buffer, []
        last = pending[-1] if pending else None
        self._resolve_handler(last).handle_batch(tuple(pending))

    @override
    def close(self) -> None:
        """Flush the passthru floor, then close the wrapped handler."""
        self._flush_state(self._state())
        self._close_handler()

    @override
    def reset(self) -> None:
        """Flush the passthru floor, reset processors, and reset the wrapped handler."""
        self._flush_state(self._state())
        self._reset_processors()
        self._reset_handler()

    def clear(self) -> None:
        """Drop the buffer without forwarding it, and start buffering afresh."""
        state = self._state()
        with self._buffer_lock:
            state.buffer = []
        self.reset()

    def _state(self) -> _FingersCrossedState:
        unit = unit_state(self, _FingersCrossedState, on_end=self._flush_state)
        return unit if unit is not None else self._instance_state

    def _flush_state(self, state: _FingersCrossedState) -> None:
        with self._buffer_lock:
            pending, state.buffer = state.buffer, []
            state.buffering = True
        if self._passthru_level is not None:
            kept = [record for record in pending if self._passthru_level.includes(record.level)]
            if kept:
                self._resolve_handler(kept[-1]).handle_batch(tuple(kept))
