"""Several transports taking turns."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from typing_extensions import override
from xtr_clock import SystemClock

from xtr_notifier.exception import LogicError, NotifierRuntimeError, TransportError

from .transport_interface import TransportInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_clock import ClockInterface

    from xtr_notifier.message import MessageInterface, SentMessage

__all__ = ["RoundRobinTransport"]


class RoundRobinTransport(TransportInterface):
    """Sends each message through the next transport in turn: ``a && b``.

    Spreads messages over several providers — or several accounts at one. A
    transport whose send raises :class:`~xtr_notifier.exception.TransportError`
    is dead: it is skipped for ``retry_period`` seconds, measured on the clock,
    and the message goes to the next one. Any other error is a mistake another
    transport would make too, so it reaches the caller at once.

    The first turn goes to a random transport, so short-lived processes that
    each send a message or two still spread them.
    """

    def __init__(
        self,
        transports: Sequence[TransportInterface],
        retry_period: float = 60,
        clock: ClockInterface | None = None,
    ) -> None:
        """Take turns between ``transports``.

        Args:
            transports: The transports, in turn order.
            retry_period: How many seconds a dead transport is skipped for.
            clock: What a dead transport's rest is measured on.

        Raises:
            LogicError: If ``transports`` is empty.
        """
        if not transports:
            raise LogicError(
                f'"{type(self).__name__}" must have at least one transport configured.'
            )
        self._transports: tuple[TransportInterface, ...] = tuple(transports)
        self._retry_period: float = retry_period
        self._clock: ClockInterface = SystemClock() if clock is None else clock
        self._dead_since: dict[int, float] = {}
        self._cursor: int | None = None

    @override
    def __str__(self) -> str:
        """Join the transports' names with the symbol that built them."""
        return f" {self._get_name_symbol()} ".join(str(transport) for transport in self._transports)

    @override
    def supports(self, message: MessageInterface) -> bool:
        """Tell whether any of the transports supports ``message``."""
        return any(transport.supports(message) for transport in self._transports)

    @override
    async def send(self, message: MessageInterface) -> SentMessage:
        """Send ``message`` through the next live transport, moving on from each that fails.

        Raises:
            LogicError: If no transport supports the message.
            NotifierRuntimeError: If every transport that supports it is dead.
        """
        if not self.supports(message):
            raise LogicError(
                f'None of the configured Transports of "{type(self).__name__}" '
                "supports the given message."
            )
        while (index := self._get_next_transport(message)) is not None:
            try:
                return await self._transports[index].send(message)
            except TransportError:
                self._dead_since[index] = self._now()
        raise NotifierRuntimeError("All transports failed.")

    def _get_next_transport(self, message: MessageInterface) -> int | None:
        """Return the index of the next live transport supporting ``message``, and move on.

        A dead transport whose rest is over is live again. ``None`` when a full
        turn finds none.
        """
        if self._cursor is None:
            self._cursor = self._get_initial_cursor()
        index = self._cursor
        while True:
            if self._transports[index].supports(message):
                dead_since = self._dead_since.get(index)
                if dead_since is None:
                    break
                if self._now() - dead_since > self._retry_period:
                    del self._dead_since[index]
                    break
            index = self._move(index)
            if index == self._cursor:
                return None
        self._cursor = self._move(index)
        return index

    def _is_transport_dead(self, index: int) -> bool:
        """Tell whether the transport at ``index`` is resting after a failure."""
        return index in self._dead_since

    def _get_initial_cursor(self) -> int:
        """Return where the first turn starts: anywhere, so restarts still spread."""
        return random.randrange(len(self._transports))  # noqa: S311 -- load spreading, not security

    def _get_name_symbol(self) -> str:
        """Return what joins the transports' names: the DSN operator that builds this."""
        return "&&"

    def _move(self, index: int) -> int:
        """Return the index after ``index``, wrapping around."""
        return (index + 1) % len(self._transports)

    def _now(self) -> float:
        """Return the clock's time, in seconds."""
        return self._clock.now().timestamp()
