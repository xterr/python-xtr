from __future__ import annotations

from xtr_notifier.message import ChatMessage, MessageOptions, SentMessage

from xtr_slack_notifier import SlackSentMessage


def _sent() -> SlackSentMessage:
    return SlackSentMessage(ChatMessage("Hello"), "slack", "C123456", "1503435956.000247")


def test_it_carries_the_channel_and_the_timestamp_as_message_id() -> None:
    sent = _sent()

    assert isinstance(sent, SentMessage)
    assert sent.channel_id == "C123456"
    assert sent.message_id == "1503435956.000247"
    assert sent.transport == "slack"


def test_it_makes_the_message_updating_it() -> None:
    update = _sent().get_update_message("Hello World", {"as_user": True})

    assert update == ChatMessage(
        "Hello World",
        MessageOptions(
            "slack.update",
            None,
            {"as_user": True, "channel": "C123456", "ts": "1503435956.000247"},
        ),
    )
