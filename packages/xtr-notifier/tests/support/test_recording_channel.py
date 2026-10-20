from __future__ import annotations

import pytest

from tests.support.recording_channel import RecordingChannel
from xtr_notifier.channel import ChannelInterface
from xtr_notifier.notification import Notification
from xtr_notifier.recipient import NoRecipient


def test_it_is_a_channel_supporting_what_it_is_told_to() -> None:
    assert isinstance(RecordingChannel(), ChannelInterface)
    assert RecordingChannel().supports(Notification(), NoRecipient())
    assert not RecordingChannel(supports=False).supports(Notification(), NoRecipient())


@pytest.mark.anyio
async def test_it_records_every_notify_in_order() -> None:
    channel = RecordingChannel()
    notification, recipient = Notification("one"), NoRecipient()

    await channel.notify(notification, recipient, "slack")
    await channel.notify(notification, recipient)

    assert channel.notified == [(notification, recipient, "slack"), (notification, recipient, None)]
