from __future__ import annotations

from tests.support.dummy_message import DummyMessage
from xtr_notifier.message import MessageInterface


def test_it_is_a_message() -> None:
    assert isinstance(DummyMessage(), MessageInterface)


def test_it_has_a_recipient_and_no_transport_by_default() -> None:
    message = DummyMessage()

    assert message.subject == "subject"
    assert message.recipient_id == "recipient_id"
    assert message.options is None
    assert message.transport is None
