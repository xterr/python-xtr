"""Building transports from DSN strings."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, final

from xtr_notifier.exception import UnsupportedSchemeError

from .dsn import Dsn
from .failover_transport import FailoverTransport
from .round_robin_transport import RoundRobinTransport
from .transports import Transports

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from .transport_factory_discovery import TransportFactoryDiscovery
    from .transport_factory_interface import TransportFactoryInterface
    from .transport_interface import TransportInterface

__all__ = ["Transport"]

_FAILOVER = re.compile(r"\s+\|\|\s+")
_ROUND_ROBIN = re.compile(r"\s+&&\s+")


@final
class Transport:
    """Turns DSN strings into transports, through the factories serving their schemes.

    One DSN builds one transport; DSNs joined by `` || `` build a
    :class:`FailoverTransport`, and by `` && `` a :class:`RoundRobinTransport`::

        transport = Transport(
            discovery=TransportFactoryDiscovery(
                TransportFactoryDiscovery.CHATTER_GROUP, http_client=client
            )
        ).from_string("slack://TOKEN@default?channel=ops || telegram://TOKEN@default")

    A scheme is looked up in the factories given first, in order, then among
    those the discovery finds installed. A chatter and a texter each have a
    builder of their own, over their own group, so a chat provider never serves
    the texter's DSNs.
    """

    __slots__ = ("_discovery", "_factories")

    def __init__(
        self,
        factories: Iterable[TransportFactoryInterface] = (),
        discovery: TransportFactoryDiscovery | None = None,
    ) -> None:
        """Build through ``factories``, then through the ones ``discovery`` finds.

        Args:
            factories: Factories tried first, in order — an application's own,
                or a provider's that needs more than discovery hands it.
            discovery: Where to look for a scheme no factory given serves;
                ``None`` uses the given factories only.
        """
        self._factories = tuple(factories)
        self._discovery = discovery

    def from_strings(self, dsns: Mapping[str, str]) -> Transports:
        """Build a transport per named DSN, picked per message by name.

        Raises:
            InvalidArgumentError: If a DSN cannot be read.
            UnsupportedSchemeError: If no factory serves a DSN's scheme.
        """
        return Transports({name: self.from_string(dsn) for name, dsn in dsns.items()})

    def from_string(self, dsn: str) -> TransportInterface:
        """Build the transport ``dsn`` describes — one, a failover, or a round robin.

        Raises:
            InvalidArgumentError: If a DSN cannot be read.
            UnsupportedSchemeError: If no factory serves a DSN's scheme.
        """
        failover = _FAILOVER.split(dsn)
        if len(failover) > 1:
            return FailoverTransport([self.from_dsn_object(Dsn(part)) for part in failover])
        round_robin = _ROUND_ROBIN.split(dsn)
        if len(round_robin) > 1:
            return RoundRobinTransport([self.from_dsn_object(Dsn(part)) for part in round_robin])
        return self.from_dsn_object(Dsn(dsn))

    def from_dsn_object(self, dsn: Dsn) -> TransportInterface:
        """Build the transport a parsed ``dsn`` describes.

        Raises:
            UnsupportedSchemeError: If no factory serves the scheme. It names the
                provider library to install when the scheme is a known one.
        """
        for factory in self._factories:
            if factory.supports(dsn):
                return factory.create(dsn)
        if self._discovery is None:
            raise UnsupportedSchemeError(dsn.scheme)
        discovered = self._discovery.factory_for(dsn)
        if discovered is None:
            raise UnsupportedSchemeError(
                dsn.scheme, self._discovery.name, self._discovery.advertised_schemes()
            )
        return discovered.create(dsn)
