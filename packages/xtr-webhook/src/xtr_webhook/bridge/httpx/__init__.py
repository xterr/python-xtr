"""The httpx bridge: the sender, and the guard against private networks.

Installed with the ``client`` extra. The sender is the one place a webhook
touches the client library; the guard is a transport wrapped around the
client's own, so it sees every outgoing request — whatever headers or url the
configurators produced — before any connection is made.
"""

from __future__ import annotations

from .httpx_sender import HttpxSender
from .no_private_network_transport import NoPrivateNetworkTransport

__all__ = [
    "HttpxSender",
    "NoPrivateNetworkTransport",
]
