"""A transport that sends nothing and does what a test scripts."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_notifier.message import SentMessage
from xtr_notifier.transport import TransportInterface

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from xtr_notifier.message import MessageInterface

__all__ = ["FakeTransport"]


@final
class FakeTransport(TransportInterface):
    """Records every message it is asked to send, and answers as scripted.

    ``outcomes`` is consumed one per send: an exception is raised, ``None``
    sends. Once it is spent, every further send succeeds.
    """

    def __init__(
        self,
        name: str = "fake",
        supports: bool | Callable[[MessageInterface], bool] = True,
        outcomes: Iterable[Exception | None] = (),
    ) -> None:
        self.name = name
        self.sent: list[MessageInterface] = []
        self.supports_asked: list[MessageInterface] = []
        self._supports = supports
        self._outcomes = list(outcomes)

    @override
    async def send(self, message: MessageInterface) -> SentMessage:
        self.sent.append(message)
        if self._outcomes:
            outcome = self._outcomes.pop(0)
            if outcome is not None:
                raise outcome
        return SentMessage(message, self.name)

    @override
    def supports(self, message: MessageInterface) -> bool:
        self.supports_asked.append(message)
        if isinstance(self._supports, bool):
            return self._supports
        return self._supports(message)

    @override
    def __str__(self) -> str:
        return f"{self.name}://local"
