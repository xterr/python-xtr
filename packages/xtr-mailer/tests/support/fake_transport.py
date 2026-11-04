"""A transport keeping what it is asked to send, or failing with the error it is given."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_mailer.transport import AbstractTransport

if TYPE_CHECKING:
    from xtr_clock import ClockInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_logging_contracts import LoggerInterface

    from xtr_mailer import SentMessage

__all__ = ["FakeTransport"]


class FakeTransport(AbstractTransport):
    """Keeps every message it sends in :attr:`sent`, or raises :attr:`error` instead."""

    def __init__(
        self,
        event_dispatcher: EventDispatcherInterface | None = None,
        logger: LoggerInterface | None = None,
        clock: ClockInterface | None = None,
    ) -> None:
        super().__init__(event_dispatcher, logger, clock)
        self.sent: list[SentMessage] = []
        self.error: Exception | None = None

    @override
    async def _do_send(self, message: SentMessage) -> None:
        if self.error is not None:
            raise self.error
        self.sent.append(message)

    @override
    def __str__(self) -> str:
        return "fake://"
