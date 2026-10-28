"""The chatter finds the Telegram factory by its scheme, through the advertised entry point."""

from __future__ import annotations

import pytest
from xtr_http_client import JsonMockResponse, MockHttpClient
from xtr_notifier import Chatter, Transport
from xtr_notifier.exception import UnsupportedSchemeError
from xtr_notifier.message import ChatMessage
from xtr_notifier.transport import TransportFactoryDiscovery

from xtr_telegram_notifier import TelegramOptions


def _transport(
    client: MockHttpClient, group: str = TransportFactoryDiscovery.CHATTER_GROUP
) -> Transport:
    return Transport(discovery=TransportFactoryDiscovery(group, http_client=client))


@pytest.mark.anyio
async def test_a_telegram_dsn_is_served_and_sends_through_the_chatter() -> None:
    client = MockHttpClient(JsonMockResponse({"ok": True, "result": {"message_id": 7}}))
    transport = _transport(client).from_string("telegram://123:TOKEN@default?channel=ops")

    sent = await Chatter(transport).send(
        ChatMessage("Deployed", TelegramOptions().disable_notification(True).to_options())
    )

    assert str(transport) == "telegram://api.telegram.org?channel=ops"
    assert sent is not None
    assert sent.message_id == "7"
    assert client.get_requests_count() == 1


def test_the_texter_does_not_serve_telegram() -> None:
    with pytest.raises(UnsupportedSchemeError, match='"telegram" scheme is not supported'):
        _ = _transport(MockHttpClient(), TransportFactoryDiscovery.TEXTER_GROUP).from_string(
            "telegram://123:TOKEN@default?channel=ops"
        )
