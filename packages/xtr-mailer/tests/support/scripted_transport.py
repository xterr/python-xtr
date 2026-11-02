"""A transport answering each send as its script says: with an error, or by sending."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_mailer import Envelope, SentMessage
from xtr_mailer.transport import TransportInterface

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterable

    from xtr_mime import RawMessage

__all__ = ["ScriptedTransport"]


class ScriptedTransport(TransportInterface):
    """Answers its n-th send with its n-th outcome: the error raised, or ``None`` to send.

    Past the end of its script it sends. :attr:`received` keeps every email it is handed, sent
    or not; :attr:`sent` what it sent. ``pause``, when given, is awaited before each answer, so
    sends can overlap or be cancelled half-way.
    """

    def __init__(
        self,
        name: str,
        outcomes: Iterable[Exception | None] = (),
        pause: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self.name: str = name
        self.received: list[RawMessage] = []
        self.sent: list[SentMessage] = []
        self._outcomes: list[Exception | None] = list(outcomes)
        self._pause: Callable[[], Awaitable[None]] | None = pause

    @override
    async def send(
        self, message: RawMessage, envelope: Envelope | None = None
    ) -> SentMessage | None:
        self.received.append(message)
        if self._pause is not None:
            await self._pause()
        if self._outcomes and (error := self._outcomes.pop(0)) is not None:
            raise error
        sent = SentMessage(message, envelope if envelope is not None else Envelope.create(message))
        self.sent.append(sent)
        return sent

    @override
    def __str__(self) -> str:
        return self.name
