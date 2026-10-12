"""The application's bus: the consume message is handled where it is dispatched."""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_messenger import MessageBusConfig, TransportConfig

from xtr_remote_event.messenger import ConsumeRemoteEventMessage


@configure
def messenger() -> MessageBusConfig:
    """Route the message to ``sync://``, so a test sees what consuming it did."""
    return MessageBusConfig(
        transports={"sync": TransportConfig("sync://")},
        routing={ConsumeRemoteEventMessage: "sync"},
    )
