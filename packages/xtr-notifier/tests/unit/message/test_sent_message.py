from __future__ import annotations

from tests.support.dummy_message import DummyMessage
from xtr_notifier.message import SentMessage


def test_it_keeps_the_message_the_transport_and_the_info() -> None:
    original = DummyMessage()

    sent = SentMessage(original, "any", {"foo": "bar"})
    sent.message_id = "the_id"

    assert sent.original_message is original
    assert sent.transport == "any"
    assert sent.message_id == "the_id"
    assert sent.info == {"foo": "bar"}
    assert sent.get_info("foo") == "bar"
    assert sent.get_info("not_existing") is None


def test_it_has_no_id_and_no_info_until_given() -> None:
    sent = SentMessage(DummyMessage(), "any")

    assert sent.message_id is None
    assert sent.info == {}


def test_it_is_built_with_the_id_the_provider_answered() -> None:
    assert SentMessage(DummyMessage(), "any", message_id="42").message_id == "42"
