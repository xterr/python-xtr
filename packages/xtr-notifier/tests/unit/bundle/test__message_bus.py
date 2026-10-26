from __future__ import annotations

import pytest
from xtr_messenger import MessageBusConfig, TransportConfig

from xtr_notifier.bundle._message_bus import routed
from xtr_notifier.message import ChatMessage, SmsMessage
from xtr_notifier.messenger import MESSAGE_NAMES

_SYNC = {"sync": TransportConfig("sync://")}


@pytest.mark.parametrize(
    "routing",
    [{ChatMessage: "sync"}, {"*": "sync"}, {MESSAGE_NAMES[ChatMessage]: "sync"}, {object: "sync"}],
)
def test_a_message_the_routing_names_is_routed(routing: dict[type | str, str]) -> None:
    assert routed(MessageBusConfig(transports=_SYNC, routing=routing), ChatMessage)


def test_a_message_the_routing_leaves_out_is_not_routed() -> None:
    config = MessageBusConfig(transports=_SYNC, routing={SmsMessage: "sync"})

    assert not routed(config, ChatMessage)


def test_every_message_is_routed_when_the_bus_handles_unrouted_ones() -> None:
    assert routed(MessageBusConfig(handle_unrouted=True), ChatMessage)
