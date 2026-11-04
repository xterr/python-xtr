"""What carries an email to its destination, and the DSN that picks it.

A :class:`TransportInterface` sends an email now; :class:`AbstractTransport` is the base that
announces it to listeners and keeps the pace. :class:`NullTransport` sends nothing anywhere,
and :class:`Transports` puts the named transports of an application behind one.
:class:`AbstractHttpTransport` is the base of a transport reaching a provider over HTTP, and
:class:`AbstractApiTransport` of one handing a provider's API an email's fields.
:class:`RoundRobinTransport` spreads email over several transports and
:class:`FailoverTransport` falls back to the next when one fails; both are a
:class:`StoppableTransportInterface`, ending the sessions their transports hold open.
:class:`SendmailTransport` hands email to the host's sendmail program, built by
:class:`SendmailTransportFactory` from a ``sendmail://`` DSN and by
:class:`NativeTransportFactory` from ``native://``, the host's own.

:class:`Transport` builds any of them from a DSN string, through the
:class:`TransportFactoryInterface` serving each scheme — given, or found installed by
:class:`TransportFactoryDiscovery`; :class:`AbstractTransportFactory` is the base of each.
"""

from __future__ import annotations

from .abstract_api_transport import AbstractApiTransport
from .abstract_http_transport import AbstractHttpTransport
from .abstract_transport import AbstractTransport
from .abstract_transport_factory import AbstractTransportFactory
from .dsn import Dsn, DsnOption
from .failover_transport import FailoverTransport
from .native_transport_factory import NativeTransportFactory
from .null_transport import NullTransport
from .null_transport_factory import NullTransportFactory
from .remote_template_transport_interface import RemoteTemplateTransportInterface
from .round_robin_transport import RoundRobinTransport
from .sendmail_transport import SendmailTransport
from .sendmail_transport_factory import SendmailTransportFactory
from .stoppable_transport_interface import StoppableTransportInterface
from .transport import Transport
from .transport_factory_discovery import TransportFactoryDiscovery
from .transport_factory_interface import TransportFactoryInterface
from .transport_interface import TransportInterface
from .transports import Transports

__all__ = [
    "AbstractApiTransport",
    "AbstractHttpTransport",
    "AbstractTransport",
    "AbstractTransportFactory",
    "Dsn",
    "DsnOption",
    "FailoverTransport",
    "NativeTransportFactory",
    "NullTransport",
    "NullTransportFactory",
    "RemoteTemplateTransportInterface",
    "RoundRobinTransport",
    "SendmailTransport",
    "SendmailTransportFactory",
    "StoppableTransportInterface",
    "Transport",
    "TransportFactoryDiscovery",
    "TransportFactoryInterface",
    "TransportInterface",
    "Transports",
]
