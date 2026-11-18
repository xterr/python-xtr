from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import cast

from xtr_http_kernel.data_collector import clone_var

from tests.support.dummy_message import DummyMessage
from xtr_notifier.data_collector import NotifiedMessage
from xtr_notifier.data_collector._masking import MASK
from xtr_notifier.exception import TransportError
from xtr_notifier.message import (
    ChatMessage,
    MessageOptions,
    NullMessage,
    PushMessage,
    SentMessage,
    SmsMessage,
)

_AT = datetime(2026, 1, 1, tzinfo=UTC)


def test_an_announced_chat_message_is_pending_with_what_it_carries() -> None:
    message = ChatMessage("Deployed", MessageOptions("slack", "C42"), transport="slack")

    notified = NotifiedMessage.announced(message, queued=False, at=_AT)

    assert notified.to_data() == {
        "message_class": "xtr_notifier.message.chat_message.ChatMessage",
        "channel": "chat",
        "transport": "slack",
        "subject": "Deployed",
        "recipient": "C42",
        "options": clone_var(MessageOptions("slack", "C42")),
        "queued": False,
        "status": "pending",
        "sent_through": None,
        "sent_message_id": None,
        "error": None,
        "duration_ms": None,
    }


def test_a_queued_message_is_recorded_as_queued() -> None:
    notified = NotifiedMessage.announced(SmsMessage("+33123", "Code"), queued=True, at=_AT)

    assert (notified.queued, notified.status) == (True, "queued")


def test_a_text_message_goes_to_its_phone_number_on_the_sms_channel() -> None:
    notified = NotifiedMessage.announced(SmsMessage("+33123", "Code"), queued=False, at=_AT)

    assert (notified.channel, notified.recipient) == ("sms", "+33123")


def test_a_push_message_is_on_the_push_channel() -> None:
    notified = NotifiedMessage.announced(PushMessage("Title", "Body"), queued=False, at=_AT)

    assert (notified.channel, notified.recipient) == ("push", None)


def test_a_message_sent_nowhere_keeps_its_class_and_the_wrapped_message_s_channel() -> None:
    message = NullMessage(SmsMessage("+33123", "Code"))

    notified = NotifiedMessage.announced(message, queued=False, at=_AT)

    assert notified.message_class == "xtr_notifier.message.null_message.NullMessage"
    assert notified.channel == "sms"


def test_a_message_of_a_kind_of_its_own_has_no_channel() -> None:
    notified = NotifiedMessage.announced(DummyMessage(), queued=False, at=_AT)

    assert notified.channel is None


def test_a_message_without_options_records_none() -> None:
    notified = NotifiedMessage.announced(ChatMessage("Hi"), queued=False, at=_AT)

    assert notified.options is None


def test_a_credential_in_the_options_is_masked() -> None:
    options = MessageOptions("telegram", values={"bot_token": "123:abc"})

    notified = NotifiedMessage.announced(ChatMessage("Hi", options), queued=False, at=_AT)

    shown = json.dumps(notified.to_data())
    assert "123:abc" not in shown
    assert MASK in shown


def test_a_sent_message_records_its_sender_its_id_and_how_long_it_took() -> None:
    message = ChatMessage("Hi")
    notified = NotifiedMessage.announced(message, queued=False, at=_AT)

    notified.mark_sent(
        SentMessage(message, "slack://default", message_id="m-1"), _AT + timedelta(milliseconds=25)
    )

    assert (notified.status, notified.sent_through, notified.sent_message_id) == (
        "sent",
        "slack://default",
        "m-1",
    )
    assert notified.duration_ms == 25.0


def test_a_failed_message_records_the_error_and_how_long_it_took() -> None:
    notified = NotifiedMessage.announced(ChatMessage("Hi"), queued=False, at=_AT)

    notified.mark_failed(TransportError("unreachable"), _AT + timedelta(milliseconds=4))

    assert (notified.status, notified.error, notified.duration_ms) == (
        "failed",
        "TransportError: unreachable",
        4.0,
    )


def test_the_profile_data_is_plain_json() -> None:
    message = ChatMessage("Hi", MessageOptions("slack", values={"blocks": [{"type": "section"}]}))
    notified = NotifiedMessage.announced(message, queued=False, at=_AT)
    notified.mark_sent(SentMessage(message, "slack://default"), _AT)

    data = notified.to_data()

    assert json.loads(json.dumps(data)) == data
    assert cast("dict[str, object]", data["options"])["kind"] == "object"
