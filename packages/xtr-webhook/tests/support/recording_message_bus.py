"""A bus that keeps what was dispatched instead of sending it anywhere.

Keeping the messages rather than counting them is what lets a test say which event
went out under which type, and in which order — the two things an endpoint fanning a
multi-event webhook out can get wrong.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_messenger import Envelope, MessageBusInterface

if TYPE_CHECKING:
    from xtr_messenger.stamp import StampInterface

__all__ = ["RecordingMessageBus"]


@final
class RecordingMessageBus(MessageBusInterface):
    """Records every dispatch in ``messages``; ``raises`` makes each one fail.

    The message is recorded before ``raises`` is thrown, so a test can tell a
    dispatch that never happened from one that happened and then failed —
    which is the difference between an event being lost and a sender being
    asked to send it again.
    """

    def __init__(self, raises: Exception | None = None) -> None:
        self.messages: list[object] = []
        self.raises = raises

    @override
    async def dispatch(self, message: object, *stamps: StampInterface) -> Envelope:
        self.messages.append(message)

        if self.raises is not None:
            raise self.raises

        return Envelope(message, stamps)
