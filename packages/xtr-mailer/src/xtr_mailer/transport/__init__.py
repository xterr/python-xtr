"""What carries an email to its destination, and the DSN that picks it.

A :class:`TransportInterface` sends an email now; :class:`AbstractTransport` is the base that
announces it to listeners and keeps the pace. :class:`NullTransport` sends nothing anywhere,
and :class:`Transports` puts the named transports of an application behind one.
:class:`RoundRobinTransport` spreads email over several transports and
:class:`FailoverTransport` falls back to the next when one fails; both are a
:class:`StoppableTransportInterface`, ending the sessions their transports hold open.
"""

from __future__ import annotations

from .abstract_transport import AbstractTransport
from .dsn import Dsn, DsnOption
from .failover_transport import FailoverTransport
from .null_transport import NullTransport
from .null_transport_factory import NullTransportFactory
from .remote_template_transport_interface import RemoteTemplateTransportInterface
from .round_robin_transport import RoundRobinTransport
from .stoppable_transport_interface import StoppableTransportInterface
from .transport_factory_interface import TransportFactoryInterface
from .transport_interface import TransportInterface
from .transports import Transports

__all__ = [
    "AbstractTransport",
    "Dsn",
    "DsnOption",
    "FailoverTransport",
    "NullTransport",
    "NullTransportFactory",
    "RemoteTemplateTransportInterface",
    "RoundRobinTransport",
    "StoppableTransportInterface",
    "TransportFactoryInterface",
    "TransportInterface",
    "Transports",
]
