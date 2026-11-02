"""Several transports taking turns."""

from __future__ import annotations

import copy
from secrets import randbelow
from typing import TYPE_CHECKING

from typing_extensions import override
from xtr_clock import SystemClock
from xtr_logging_contracts import EXCEPTION_KEY, NullLogger

from xtr_mailer._error_text import type_name
from xtr_mailer.exception import TransportError

from .stoppable_transport_interface import StoppableTransportInterface

if TYPE_CHECKING:
    from collections.abc import Sequence
    from collections.abc import Set as AbstractSet

    from xtr_clock import ClockInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_mime import RawMessage

    from xtr_mailer.envelope import Envelope
    from xtr_mailer.sent_message import SentMessage

    from .transport_interface import TransportInterface

__all__ = ["RoundRobinTransport"]


class RoundRobinTransport(StoppableTransportInterface):
    """Sends each email through the next transport in turn: ``roundrobin(a b)``.

    Spreads email over several servers or providers. A transport whose send raises
    :class:`~xtr_mailer.exception.TransportError` is dead: it is skipped for ``retry_period``
    seconds, measured on the clock, and the email goes to the next one. Any other error is a
    mistake another transport would make too, so it reaches the caller at once; a cancelled send
    is neither, and reaches the caller as it is — the transport stays live, and the email is not
    tried elsewhere, since whether it reached the server is unknown.

    One send tries each transport at most once: a transport whose rest runs out while the
    others are tried is not tried again for the same email, so a send ends however long each
    try takes.

    The first turn goes to a random transport, so short-lived processes that each send an email
    or two still spread them. Sends may overlap: picking a transport, and marking one dead, each
    happen with no await in the middle, so no two sends see the turn half-moved.

    Thread safety: one event loop. The turn and the dead transports are kept with no lock, so
    every send through one transport runs on the same event loop.
    """

    def __init__(
        self,
        transports: Sequence[TransportInterface],
        retry_period: float = 60,
        *,
        logger: LoggerInterface | None = None,
        clock: ClockInterface | None = None,
    ) -> None:
        """Take turns between ``transports``.

        Args:
            transports: The transports, in turn order.
            retry_period: How many seconds a dead transport is skipped for.
            logger: Where each failure of a transport is logged; ``None`` logs nothing.
            clock: What a dead transport's rest is measured on.

        Raises:
            TransportError: ``transports`` is empty.
        """
        if not transports:
            raise TransportError(
                f'"{type_name(type(self))}" must have at least one transport configured.'
            )
        self._transports: tuple[TransportInterface, ...] = tuple(transports)
        self._retry_period: float = retry_period
        self._logger: LoggerInterface = logger if logger is not None else NullLogger()
        self._clock: ClockInterface = clock if clock is not None else SystemClock()
        self._dead_since: dict[int, float] = {}
        self._cursor: int | None = None

    @override
    async def send(
        self, message: RawMessage, envelope: Envelope | None = None
    ) -> SentMessage | None:
        """Send a copy of ``message`` through the next live transport, moving on from each failure.

        Each transport gets a copy of its own, so one failing half-way through changing the
        email hands the next one the email as it was given.

        Raises:
            TransportError: Every transport failed — the error's ``debug`` holds what each one
                said — or every one is dead already.
        """
        error: TransportError | None = None
        tried: set[int] = set()
        while (transport := self._get_next_transport(tried)) is not None:
            tried.add(id(transport))
            try:
                return await transport.send(copy.copy(message), envelope)
            except TransportError as failure:
                if error is None:
                    error = TransportError("All transports failed.")
                error.append_debug(f'Transport "{transport}": {failure.debug}\n')
                self._logger.error(  # noqa: TRY400 -- the error goes in the context, by contract
                    'Transport "{transport}" failed.',
                    {"transport": str(transport), EXCEPTION_KEY: failure},
                )
                self._dead_since[id(transport)] = self._now()
        raise error if error is not None else TransportError("No transports found.")

    @override
    async def stop(self) -> None:
        """Stop each transport that holds a session open, nested groups included.

        One failing to stop does not keep the others open: each is stopped, then the first
        error is raised.
        """
        error: Exception | None = None
        for transport in self._transports:
            if isinstance(transport, StoppableTransportInterface):
                try:
                    await transport.stop()
                except Exception as failure:  # noqa: BLE001 -- raised once the others are stopped
                    error = failure if error is None else error
        if error is not None:
            raise error

    @override
    def __str__(self) -> str:
        """Name it after its transports, the way a DSN groups them: ``roundrobin(a b)``."""
        names = " ".join(str(transport) for transport in self._transports)
        return f"{self._get_name_symbol()}({names})"

    def _get_next_transport(self, tried: AbstractSet[int]) -> TransportInterface | None:
        """Return the next live transport not in ``tried``, and move the turn past it.

        A dead transport whose rest is over is live again. ``tried`` holds the ``id`` of each
        transport the current send went through already. ``None`` when a full turn finds none.
        """
        if self._cursor is None:
            self._cursor = self._get_initial_cursor()
        cursor = self._cursor
        while True:
            transport = self._transports[cursor]
            key = id(transport)
            if key not in tried:
                dead_since = self._dead_since.get(key)
                if dead_since is None:
                    break
                if self._now() - dead_since > self._retry_period:
                    del self._dead_since[key]
                    break
            cursor = self._move(cursor)
            if cursor == self._cursor:
                return None
        self._cursor = self._move(cursor)
        return transport

    def _is_transport_dead(self, transport: TransportInterface) -> bool:
        """Tell whether ``transport`` is resting after a failure."""
        return id(transport) in self._dead_since

    def _get_initial_cursor(self) -> int:
        """Return where the first turn starts: anywhere, so short-lived processes still spread."""
        return randbelow(len(self._transports))

    def _get_name_symbol(self) -> str:
        """Return the name of the DSN group that builds this transport."""
        return "roundrobin"

    def _move(self, cursor: int) -> int:
        """Return the position after ``cursor``, wrapping around."""
        return (cursor + 1) % len(self._transports)

    def _now(self) -> float:
        """Return the clock's time, in seconds."""
        return self._clock.now().timestamp()
