from __future__ import annotations

import pytest
from xtr_messenger import MessageBusConfig, TransportConfig, name_of

from xtr_mailer.bundle._message_bus import routed
from xtr_mailer.messenger import SendEmailMessage

_TRANSPORTS = {"mail": TransportConfig("in-memory://")}


@pytest.mark.parametrize("key", [SendEmailMessage, object, "*", name_of(SendEmailMessage)], ids=str)
def test_an_email_the_routing_names_is_queued(key: type | str) -> None:
    assert routed(MessageBusConfig(transports=_TRANSPORTS, routing={key: "mail"}))


def test_an_email_handled_unrouted_is_queued() -> None:
    assert routed(MessageBusConfig(handle_unrouted=True))


def test_an_email_the_routing_does_not_name_is_sent_at_once() -> None:
    assert not routed(MessageBusConfig(transports=_TRANSPORTS, routing={"other": "mail"}))
