"""The chatter finds the Slack factory by its scheme, through the advertised entry point."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_http_client import JsonMockResponse, MockHttpClient, MockResponse
from xtr_notifier import Chatter, Transport
from xtr_notifier.exception import UnsupportedSchemeError
from xtr_notifier.message import ChatMessage
from xtr_notifier.notification import Importance, Notification
from xtr_notifier.transport import TransportFactoryDiscovery

if TYPE_CHECKING:
    from xtr_http_client_contracts import RequestOptions


def _transport(
    client: MockHttpClient, group: str = TransportFactoryDiscovery.CHATTER_GROUP
) -> Transport:
    return Transport(discovery=TransportFactoryDiscovery(group, http_client=client))


@pytest.mark.anyio
async def test_a_slack_dsn_is_served_and_sends_a_notification_through_the_chatter() -> None:
    def answer(_verb: str, url: str, options: RequestOptions) -> MockResponse:
        assert url == "https://slack.com/api/chat.postMessage"
        body = options.get("json")
        assert isinstance(body, dict)
        assert body["channel"] == "ops"
        assert body["text"] == "Disk almost full"
        return JsonMockResponse({"ok": True, "ts": "1.2", "channel": "C1"})

    client = MockHttpClient(answer)
    transport = _transport(client).from_string("slack://xoxb-TOKEN@default?channel=ops")

    sent = await Chatter(transport).send(
        ChatMessage.from_notification(
            Notification("Disk almost full", importance=Importance.URGENT)
        )
    )

    assert str(transport) == "slack://slack.com?channel=ops"
    assert sent is not None
    assert sent.message_id == "1.2"
    assert client.get_requests_count() == 1


def test_the_texter_does_not_serve_slack() -> None:
    with pytest.raises(UnsupportedSchemeError, match='"slack" scheme is not supported'):
        _ = _transport(MockHttpClient(), TransportFactoryDiscovery.TEXTER_GROUP).from_string(
            "slack://xoxb-TOKEN@default?channel=ops"
        )
