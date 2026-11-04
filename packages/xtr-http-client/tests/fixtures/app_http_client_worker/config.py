"""Every ping queued in memory for a worker; the HTTP client configured as it comes."""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_messenger import MessageBusConfig, TransportConfig

from .messages import Ping


@configure
def messenger() -> MessageBusConfig:
    return MessageBusConfig(
        transports={"pings": TransportConfig("in-memory://")}, routing={Ping: "pings"}
    )
