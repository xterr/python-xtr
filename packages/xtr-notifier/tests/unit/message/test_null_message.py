from __future__ import annotations

import pytest

from tests.support.dummy_message import DummyMessage
from xtr_notifier.message import MessageInterface, MessageOptions, NullMessage


@pytest.mark.parametrize(
    "message",
    [
        DummyMessage(),
        DummyMessage(transport="transport", options=MessageOptions("test", "recipient_id")),
    ],
)
def test_it_reads_through_to_the_message_it_wraps(message: DummyMessage) -> None:
    null_message = NullMessage(message)

    assert isinstance(null_message, MessageInterface)
    assert null_message.message is message
    assert null_message.subject == message.subject
    assert null_message.recipient_id == message.recipient_id
    assert null_message.options is message.options
    assert null_message.transport == message.transport
