from __future__ import annotations

from xtr_notifier.message import MessageInterface, SentMessage
from xtr_notifier.transport import TransportInterface


class _Structural:
    async def send(self, message: MessageInterface) -> SentMessage:
        return SentMessage(message, str(self))

    def supports(self, message: MessageInterface) -> bool:
        return bool(message.subject)


def test_anything_that_sends_and_says_what_it_supports_is_a_transport() -> None:
    assert isinstance(_Structural(), TransportInterface)


def test_something_that_cannot_send_is_not_a_transport() -> None:
    assert not isinstance(object(), TransportInterface)
