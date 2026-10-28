from __future__ import annotations

import pytest
from typing_extensions import override

from tests.support.fake_transport import FakeTransport
from tests.support.recording_message_bus import RecordingMessageBus
from xtr_notifier.channel import AbstractChannel, ChannelInterface
from xtr_notifier.exception import LogicError
from xtr_notifier.message import ChatMessage
from xtr_notifier.notification import Notification
from xtr_notifier.recipient import NoRecipient, RecipientInterface

pytestmark = pytest.mark.anyio


class _DummyChannel(AbstractChannel):
    @override
    async def notify(
        self,
        notification: Notification,
        recipient: RecipientInterface,
        transport_name: str | None = None,
    ) -> None:
        await self._deliver(ChatMessage(notification.subject, transport=transport_name))

    @override
    def supports(self, notification: Notification, recipient: RecipientInterface) -> bool:
        return False


def test_it_cannot_be_built_without_a_transport_and_without_a_bus() -> None:
    with pytest.raises(LogicError) as caught:
        _ = _DummyChannel()

    assert (
        str(caught.value) == '"_DummyChannel" needs a Transport or a Bus but both cannot be "None".'
    )


async def test_it_delivers_through_its_transport_without_a_bus() -> None:
    transport = FakeTransport()
    channel = _DummyChannel(transport)

    await channel.notify(Notification("Hello"), NoRecipient())

    assert isinstance(channel, ChannelInterface)
    assert [message.subject for message in transport.sent] == ["Hello"]


async def test_it_delivers_to_the_bus_when_it_has_one() -> None:
    transport = FakeTransport()
    bus = RecordingMessageBus()

    await _DummyChannel(transport, bus).notify(Notification("Hello"), NoRecipient())

    assert bus.messages == [ChatMessage("Hello")]
    assert transport.sent == []
