"""Transports: what sends a message to a provider, and the DSNs that configure them."""

from __future__ import annotations

from .abstract_transport import AbstractTransport
from .dsn import Dsn
from .null_transport import NullTransport
from .transport_interface import TransportInterface
from .transports import Transports

__all__ = ["AbstractTransport", "Dsn", "NullTransport", "TransportInterface", "Transports"]
