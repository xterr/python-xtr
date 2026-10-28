from __future__ import annotations

from xtr_notifier.message import MessageOptions

from xtr_slack_notifier import SlackOptions, UpdateMessageSlackOptions


def test_it_names_the_message_to_update_and_renders_the_update_kind() -> None:
    options = UpdateMessageSlackOptions("C123456", "1503435956.000247", {"as_user": True})

    assert options.to_options() == MessageOptions(
        "slack.update",
        None,
        {"as_user": True, "channel": "C123456", "ts": "1503435956.000247"},
    )


def test_it_is_slack_options() -> None:
    assert isinstance(UpdateMessageSlackOptions("C1", "1"), SlackOptions)


def test_its_setters_keep_the_update_kind() -> None:
    options = UpdateMessageSlackOptions("C1", "1").username("bot")

    assert options.to_options().kind == "slack.update"
