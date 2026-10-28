from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_http_client import JsonMockResponse, MockHttpClient, MockResponse
from xtr_notifier.exception import InvalidArgumentError, TransportError
from xtr_notifier.message import ChatMessage, MessageOptions, PushMessage, SmsMessage
from xtr_notifier.notification import Notification, NotificationSummary
from xtr_notifier.testing import TransportCases, assert_transport_cases

from xtr_slack_notifier import SlackOptions, SlackSentMessage, SlackTransport
from xtr_slack_notifier.block import SlackPlainTextInputBlock, SlackSectionBlock

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_client_contracts import RequestOptions

_POSTED = {"ok": True, "ts": "1503435956.000247", "channel": "C123456"}


def _transport(client: MockHttpClient | None = None, channel: str | None = None) -> SlackTransport:
    return SlackTransport("xoxb-TestToken", channel, client or MockHttpClient())


def _expecting(json: Mapping[str, object], method: str = "chat.postMessage") -> MockHttpClient:
    def answer(verb: str, url: str, options: RequestOptions) -> MockResponse:
        assert verb == "POST"
        assert url == f"https://slack.com/api/{method}"
        assert options.get("json") == json
        assert options.get("auth_bearer") == "xoxb-TestToken"
        return JsonMockResponse(_POSTED)

    return MockHttpClient(answer)


@pytest.mark.anyio
async def test_it_does_what_every_transport_owes() -> None:
    await assert_transport_cases(
        TransportCases(
            create_transport=_transport,
            to_string=[
                ("slack://slack.com", _transport()),
                ("slack://slack.com?channel=test+Channel", _transport(None, "test Channel")),
                ("slack://slack.com", _transport(None, "")),
            ],
            supported=[
                ChatMessage("Hello!"),
                ChatMessage("Hello!", SlackOptions().to_options()),
                ChatMessage("Hello!", MessageOptions("slack.update")),
            ],
            unsupported=[SmsMessage("0611223344", "Hello!"), PushMessage("Hello!", "")],
        )
    )


def test_it_refuses_a_chat_message_carrying_another_providers_options() -> None:
    assert not _transport().supports(ChatMessage("Hello!", MessageOptions("telegram")))


def test_it_refuses_a_token_slack_does_not_issue() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = SlackTransport("token", "testChannel", MockHttpClient())

    assert str(raised.value) == (
        'A valid Slack token needs to start with "xoxb-", "xoxp-" or "xoxa-2". '
        "See https://api.slack.com/authentication/token-types for further information."
    )


@pytest.mark.parametrize("token", ["xoxb-1", "xoxp-1", "xoxa-2-1"])
def test_it_takes_every_token_kind_slack_issues(token: str) -> None:
    assert str(SlackTransport(token, None, MockHttpClient())) == "slack://slack.com"


def test_its_string_form_never_shows_the_token() -> None:
    transport = SlackTransport("xoxb-SECRET", "C1", MockHttpClient())

    assert "SECRET" not in str(transport)
    assert "SECRET" not in repr(transport)


@pytest.mark.anyio
async def test_an_error_status_with_an_empty_body_is_a_transport_error() -> None:
    client = MockHttpClient(MockResponse("[]", {"http_code": 500}))

    with pytest.raises(TransportError) as raised:
        _ = await _transport(client, "testChannel").send(ChatMessage("testMessage"))

    assert str(raised.value) == 'Unable to post the Slack message: "[]".'


@pytest.mark.anyio
async def test_an_error_status_names_the_body() -> None:
    client = MockHttpClient(MockResponse('{"error":"testErrorCode"}', {"http_code": 400}))

    with pytest.raises(TransportError, match="testErrorCode"):
        _ = await _transport(client, "testChannel").send(ChatMessage("testMessage"))


@pytest.mark.anyio
async def test_an_unreachable_server_is_a_transport_error() -> None:
    client = MockHttpClient(MockResponse(info={"error": "Could not resolve host."}))

    with pytest.raises(TransportError, match=r"^Could not reach the remote Slack server\.$"):
        _ = await _transport(client, "testChannel").send(ChatMessage("testMessage"))


@pytest.mark.anyio
async def test_it_posts_a_message_and_reports_its_channel_and_timestamp() -> None:
    client = _expecting({"channel": "testChannel", "text": "testMessage"})

    sent = await _transport(client, "testChannel").send(ChatMessage("testMessage"))

    assert isinstance(sent, SlackSentMessage)
    assert sent.message_id == "1503435956.000247"
    assert sent.channel_id == "C123456"
    assert sent.transport == "slack://slack.com?channel=testChannel"


@pytest.mark.anyio
async def test_it_renders_a_notification_without_options() -> None:
    notification = Notification("testMessage")
    blocks = SlackOptions.from_notification(
        NotificationSummary.from_notification(notification)
    ).to_options()
    client = _expecting(
        {"blocks": blocks.values["blocks"], "channel": "testChannel", "text": "testMessage"}
    )

    sent = await _transport(client, "testChannel").send(ChatMessage.from_notification(notification))

    assert sent.message_id == "1503435956.000247"


@pytest.mark.parametrize("value", [True, False])
@pytest.mark.anyio
async def test_it_keeps_a_boolean_option_whatever_its_value(value: bool) -> None:
    options = (
        SlackOptions()
        .as_user(value)
        .link_names(value)
        .mrkdwn(value)
        .unfurl_links(value)
        .unfurl_media(value)
    )
    message = ChatMessage.from_notification(Notification("testMessage")).with_options(
        options.to_options()
    )
    client = _expecting(
        {
            "as_user": value,
            "link_names": value,
            "mrkdwn": value,
            "unfurl_links": value,
            "unfurl_media": value,
            "channel": "testChannel",
            "text": "testMessage",
        }
    )

    _ = await _transport(client, "testChannel").send(message)


@pytest.mark.anyio
async def test_an_answer_that_is_not_ok_is_a_transport_error() -> None:
    client = MockHttpClient(JsonMockResponse({"ok": False, "error": "testErrorCode"}))

    with pytest.raises(TransportError) as raised:
        _ = await _transport(client, "testChannel").send(ChatMessage("testMessage"))

    assert str(raised.value) == 'Unable to post the Slack message: "testErrorCode".'


@pytest.mark.anyio
async def test_it_sends_json_with_a_utf8_charset() -> None:
    def answer(_verb: str, _url: str, options: RequestOptions) -> MockResponse:
        assert options.get("headers") == {"Content-Type": "application/json; charset=utf-8"}
        return JsonMockResponse(_POSTED)

    _ = await _transport(MockHttpClient(answer)).send(ChatMessage("testMessage"))


@pytest.mark.anyio
async def test_an_answer_that_is_not_ok_lists_its_errors() -> None:
    client = MockHttpClient(
        JsonMockResponse(
            {
                "ok": False,
                "error": "invalid_blocks",
                "errors": ["no more than 50 items allowed [json-pointer:/blocks]"],
            }
        )
    )

    with pytest.raises(TransportError) as raised:
        _ = await _transport(client, "testChannel").send(ChatMessage("testMessage"))

    assert str(raised.value) == (
        'Unable to post the Slack message: "invalid_blocks" '
        "(no more than 50 items allowed [json-pointer:/blocks])."
    )


@pytest.mark.anyio
async def test_it_updates_a_sent_message() -> None:
    sent = SlackSentMessage(ChatMessage("Hello"), "slack", "C123456", "1503435956.000247")
    client = _expecting(
        {"channel": "C123456", "ts": "1503435956.000247", "text": "Hello World"}, "chat.update"
    )

    updated = await _transport(client, "another-channel").send(
        sent.get_update_message("Hello World")
    )

    assert updated.message_id == "1503435956.000247"


@pytest.mark.anyio
async def test_it_schedules_a_message_with_post_at() -> None:
    client = _expecting(
        {"post_at": 1767225600, "channel": "C1", "text": "Later"}, "chat.scheduleMessage"
    )

    _ = await _transport(client, "C1").send(
        ChatMessage("Later", SlackOptions({"post_at": 1767225600}).to_options())
    )


@pytest.mark.anyio
async def test_the_recipient_wins_over_the_dsn_channel() -> None:
    client = _expecting({"channel": "C9", "text": "Hi"})

    _ = await _transport(client, "C1").send(
        ChatMessage("Hi", SlackOptions().recipient("C9").to_options())
    )


@pytest.mark.anyio
async def test_it_sends_an_input_block() -> None:
    options = (
        SlackOptions()
        .block(SlackSectionBlock().text("testMessage"))
        .block(SlackPlainTextInputBlock("Time spent", "time_spent_input", "Enter some text here"))
    )
    client = _expecting(
        {
            "blocks": options.to_options().values["blocks"],
            "channel": "testChannel",
            "text": "testMessage",
        }
    )

    sent = await _transport(client, "testChannel").send(
        ChatMessage("testMessage", options.to_options())
    )

    assert sent.message_id == "1503435956.000247"


@pytest.mark.anyio
async def test_empty_values_are_dropped_but_zero_and_false_are_kept() -> None:
    options = SlackOptions(
        {"username": "", "blocks": [], "parse": None, "metadata": {}, "as_user": False, "n": 0}
    )
    client = _expecting({"as_user": False, "n": 0, "channel": "C1", "text": "Hi"})

    _ = await _transport(client, "C1").send(ChatMessage("Hi", options.to_options()))
