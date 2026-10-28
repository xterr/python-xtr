from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

import pytest
from xtr_notifier.exception import LogicError
from xtr_notifier.message import MessageOptions, MessageOptionsInterface
from xtr_notifier.notification import NotificationSummary

from xtr_slack_notifier import SlackOptions
from xtr_slack_notifier.block import SlackDividerBlock, SlackSectionBlock

if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        pytest.param({}, {}, id="empty is allowed"),
        pytest.param({"recipient_id": "42"}, {}, id="always unset recipient_id"),
        pytest.param(
            {"blocks": [{"type": "divider"}]}, {"blocks": [{"type": "divider"}]}, id="one block"
        ),
        *(
            pytest.param({key: value}, {key: value}, id=key)
            for key, value in (
                ("as_user", True),
                ("icon_emoji", "foo"),
                ("icon_url", "https://example.com"),
                ("link_names", True),
                ("mrkdwn", True),
                ("parse", "bar"),
                ("unfurl_links", True),
                ("unfurl_media", True),
                ("username", "baz"),
                ("thread_ts", "1503435956.000247"),
            )
        ),
    ],
)
def test_it_renders_the_options_given_without_the_recipient(
    options: dict[str, object], expected: dict[str, object]
) -> None:
    assert SlackOptions(options).to_options().values == expected


@pytest.mark.parametrize(
    ("expected", "options"),
    [
        (None, SlackOptions()),
        (None, SlackOptions({"recipient_id": None})),
        ("foo", SlackOptions().recipient("foo")),
        ("foo", SlackOptions({"recipient_id": "foo"})),
    ],
)
def test_it_reads_the_recipient(expected: str | None, options: SlackOptions) -> None:
    assert options.recipient_id == expected
    assert options.to_options().recipient_id == expected


@pytest.mark.parametrize(
    ("setter", "key", "value"),
    [
        (SlackOptions.as_user, "as_user", True),
        (SlackOptions.icon_emoji, "icon_emoji", "foo"),
        (SlackOptions.icon_url, "icon_url", "https://example.com"),
        (SlackOptions.link_names, "link_names", True),
        (SlackOptions.mrkdwn, "mrkdwn", True),
        (SlackOptions.parse, "parse", "bar"),
        (SlackOptions.unfurl_links, "unfurl_links", True),
        (SlackOptions.unfurl_media, "unfurl_media", True),
        (SlackOptions.username, "username", "baz"),
        (SlackOptions.thread_ts, "thread_ts", "1503435956.000247"),
    ],
)
def test_each_setter_sets_its_option(
    setter: Callable[[SlackOptions, object], SlackOptions], key: str, value: object
) -> None:
    options = SlackOptions()

    returned = setter(options, value)

    assert returned is options
    assert options.to_options().values[key] == value


def test_it_schedules_at_a_unix_timestamp() -> None:
    options = SlackOptions().post_at(datetime(2026, 1, 1, tzinfo=UTC))

    assert options.to_options().values == {"post_at": 1767225600}


def test_it_adds_a_block() -> None:
    options = SlackOptions().block(SlackDividerBlock())

    assert options.to_options().values["blocks"] == [{"type": "divider"}]


def test_it_renders_the_slack_kind() -> None:
    assert SlackOptions().recipient("C1").to_options() == MessageOptions("slack", "C1", {})


def test_it_is_a_message_options_builder() -> None:
    assert isinstance(SlackOptions(), MessageOptionsInterface)


@pytest.mark.parametrize(
    ("summary", "expected"),
    [
        pytest.param(
            NotificationSummary("Hi!", emoji="🌧️"),
            {
                "icon_emoji": "🌧️",
                "blocks": [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "Hi!", "verbatim": False},
                    }
                ],
            },
            id="without content + without exception",
        ),
        pytest.param(
            NotificationSummary("Hi!", content="Content here ...", emoji="🌧️"),
            {
                "icon_emoji": "🌧️",
                "blocks": [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "Hi!", "verbatim": False},
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "Content here ...", "verbatim": False},
                    },
                ],
            },
            id="with content + without exception",
        ),
        pytest.param(
            NotificationSummary("Hi!", exception_as_string="Traceback ..."),
            {
                "icon_emoji": "",
                "blocks": [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "Hi!", "verbatim": False},
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "Traceback ...", "verbatim": False},
                    },
                ],
            },
            id="with an exception",
        ),
    ],
)
def test_it_renders_a_notification(summary: NotificationSummary, expected: object) -> None:
    assert SlackOptions.from_notification(summary).to_options().values == expected


def test_it_takes_up_to_fifty_blocks_when_built() -> None:
    options = SlackOptions({"blocks": [{"type": "divider"}] * 50})

    assert len(_blocks(options)) == 50


def test_it_refuses_more_than_fifty_blocks_when_built() -> None:
    with pytest.raises(LogicError, match=r'^Maximum number of "blocks" has been reached \(50\)\.$'):
        _ = SlackOptions({"blocks": [{"type": "divider"}] * 51})


def test_it_adds_up_to_fifty_blocks() -> None:
    options = SlackOptions()
    for _ in range(50):
        _ = options.block(SlackSectionBlock())

    assert len(_blocks(options)) == 50


def test_it_refuses_a_fifty_first_block() -> None:
    options = SlackOptions()
    for _ in range(50):
        _ = options.block(SlackSectionBlock())

    with pytest.raises(LogicError, match=r'^Maximum number of "blocks" has been reached \(50\)\.$'):
        _ = options.block(SlackSectionBlock())


def test_the_rendered_options_do_not_change_with_the_builder() -> None:
    options = SlackOptions().block(SlackDividerBlock())
    rendered = options.to_options()

    _ = options.block(SlackDividerBlock())

    assert rendered.values == {"blocks": [{"type": "divider"}]}


def _blocks(options: SlackOptions) -> list[object]:
    blocks = options.to_options().values["blocks"]
    assert isinstance(blocks, list)
    return list(cast("list[object]", blocks))
