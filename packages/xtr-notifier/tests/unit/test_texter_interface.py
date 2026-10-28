from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_notifier import TexterInterface

if TYPE_CHECKING:
    from xtr_notifier.message import MessageInterface, SentMessage


class _Structural:
    async def send(self, message: MessageInterface) -> SentMessage | None:
        del message

    def supports(self, message: MessageInterface) -> bool:
        return bool(message.subject)


def test_anything_that_sends_and_says_what_it_supports_is_a_texter() -> None:
    assert isinstance(_Structural(), TexterInterface)


def test_something_that_cannot_send_is_not_a_texter() -> None:
    assert not isinstance(object(), TexterInterface)
