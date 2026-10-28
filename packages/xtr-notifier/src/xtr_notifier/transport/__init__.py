"""Transports: what sends a message to a provider, and the DSNs that configure them."""

from __future__ import annotations

from .abstract_transport import AbstractTransport
from .abstract_transport_factory import AbstractTransportFactory
from .dsn import Dsn
from .failover_transport import FailoverTransport
from .null_transport import NullTransport
from .null_transport_factory import NullTransportFactory
from .round_robin_transport import RoundRobinTransport
from .transport import Transport
from .transport_factory_discovery import TransportFactoryDiscovery
from .transport_factory_interface import TransportFactoryInterface
from .transport_interface import TransportInterface
from .transports import Transports

__all__ = [
    "AbstractTransport",
    "AbstractTransportFactory",
    "Dsn",
    "FailoverTransport",
    "NullTransport",
    "NullTransportFactory",
    "RoundRobinTransport",
    "Transport",
    "TransportFactoryDiscovery",
    "TransportFactoryInterface",
    "TransportInterface",
    "Transports",
]
