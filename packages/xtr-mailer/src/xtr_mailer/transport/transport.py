"""Building transports from DSN strings."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_mailer.exception import InvalidArgumentError, UnsupportedSchemeError

from ._dsn_grammar import GARBAGE, read_dsn_groups
from .abstract_transport import AbstractTransport
from .dsn import Dsn
from .failover_transport import FailoverTransport
from .round_robin_transport import RoundRobinTransport
from .transport_factory_discovery import TransportFactoryDiscovery
from .transports import Transports

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_client_contracts import HttpClientInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_rate_limiter import RateLimiterFactoryInterface

    from ._dsn_grammar import DsnGroup, DsnNode
    from .transport_factory_interface import TransportFactoryInterface
    from .transport_interface import TransportInterface

__all__ = ["Transport"]


@final
class Transport:
    """Turns DSN strings into transports, through the factories serving their schemes.

    One DSN builds one transport; the keywords ``failover(...)`` and ``roundrobin(...)`` group
    DSNs separated by spaces into a :class:`FailoverTransport` or a
    :class:`RoundRobinTransport`, nesting as deep as needed, each group optionally followed by
    the seconds a failed member rests for::

        transport = Transport.from_dsn(
            "roundrobin(smtp://a failover(smtp://b smtp://c))?retry_period=15",
            event_dispatcher=dispatcher,
        )

    A scheme is looked up in the factories given first, in order, then among those the
    discovery finds installed. The DSN strings carry credentials: none is kept, and no error
    raised here quotes one.

    A group logs each member that fails, through the logger the builder is given.
    """

    __slots__ = ("_discovery", "_factories", "_logger", "_rate_limiter_factories")

    def __init__(
        self,
        factories: Iterable[TransportFactoryInterface] = (),
        discovery: TransportFactoryDiscovery | None = None,
        *,
        rate_limiter_factories: Mapping[str, RateLimiterFactoryInterface] | None = None,
        logger: LoggerInterface | None = None,
    ) -> None:
        """Build through ``factories``, then through the ones ``discovery`` finds.

        Args:
            factories: Factories tried first, in order — an application's own, or one needing
                more than discovery hands it.
            discovery: Where to look for a scheme no factory given serves; ``None`` uses the
                given factories only.
            rate_limiter_factories: The limiter each named transport of :meth:`from_strings`
                is capped by, keyed by its name; a name not listed is not capped.
            logger: Where each group built logs a member that fails; ``None`` logs nothing.
                The members log where their factory was told to.
        """
        self._factories: tuple[TransportFactoryInterface, ...] = tuple(factories)
        self._discovery: TransportFactoryDiscovery | None = discovery
        self._rate_limiter_factories: Mapping[str, RateLimiterFactoryInterface] = (
            rate_limiter_factories or {}
        )
        self._logger: LoggerInterface | None = logger

    @classmethod
    def from_dsn(
        cls,
        dsn: str,
        event_dispatcher: EventDispatcherInterface | None = None,
        http_client: HttpClientInterface | None = None,
        logger: LoggerInterface | None = None,
    ) -> TransportInterface:
        """Build the transport ``dsn`` describes through the installed factories.

        Args:
            dsn: One DSN, or a keyword group of them.
            event_dispatcher: Where the transports built announce emails.
            http_client: What transports reaching their provider over HTTP use; a scheme
                needing one is refused without it.
            logger: Where the transports built log, groups included.

        Raises:
            InvalidArgumentError: ``dsn`` cannot be read.
            UnsupportedSchemeError: No installed factory serves a scheme it names.
            LogicError: A scheme's factory needs an HTTP client and none was given.
        """
        return cls._discovering(event_dispatcher, http_client, logger).from_string(dsn)

    @classmethod
    def from_dsns(
        cls,
        dsns: Mapping[str, str],
        event_dispatcher: EventDispatcherInterface | None = None,
        http_client: HttpClientInterface | None = None,
        logger: LoggerInterface | None = None,
    ) -> Transports:
        """Build a transport per named DSN through the installed factories, as :meth:`from_dsn`.

        Raises:
            InvalidArgumentError: A DSN cannot be read.
            UnsupportedSchemeError: No installed factory serves a scheme one names.
            LogicError: A scheme's factory needs an HTTP client and none was given.
            LogicError: ``dsns`` is empty.
        """
        return cls._discovering(event_dispatcher, http_client, logger).from_strings(dsns)

    def from_strings(self, dsns: Mapping[str, str]) -> Transports:
        """Build a transport per named DSN, picked per email by name, the first by default.

        Each is capped by the rate limiter given for its name, if any.

        Raises:
            InvalidArgumentError: A DSN cannot be read.
            UnsupportedSchemeError: No factory serves a scheme one names.
            LogicError: ``dsns`` is empty.
        """
        return Transports(
            {
                name: self.from_string(dsn, self._rate_limiter_factories.get(name))
                for name, dsn in dsns.items()
            }
        )

    def from_string(
        self, dsn: str, rate_limiter_factory: RateLimiterFactoryInterface | None = None
    ) -> TransportInterface:
        """Build the transport ``dsn`` describes — one, or a keyword group of them.

        Args:
            dsn: One DSN, or a keyword group of them.
            rate_limiter_factory: Caps the transport built, when it is one that can be capped.

        Raises:
            InvalidArgumentError: ``dsn`` cannot be read.
            UnsupportedSchemeError: No factory serves a scheme it names.
        """
        node, complete = read_dsn_groups(dsn)
        transport = self._build(node)
        if not complete:
            raise InvalidArgumentError(GARBAGE)
        if rate_limiter_factory is not None and isinstance(transport, AbstractTransport):
            _ = transport.set_rate_limiter_factory(rate_limiter_factory)
        return transport

    def from_dsn_object(self, dsn: Dsn) -> TransportInterface:
        """Build the transport a parsed ``dsn`` describes.

        Raises:
            UnsupportedSchemeError: No factory serves the scheme. It names the provider library
                to install when the scheme is a known one.
        """
        for factory in self._factories:
            if factory.supports(dsn):
                return factory.create(dsn)
        discovered = None if self._discovery is None else self._discovery.factory_for(dsn)
        if discovered is None:
            raise UnsupportedSchemeError(dsn.scheme)
        return discovered.create(dsn)

    @classmethod
    def _discovering(
        cls,
        event_dispatcher: EventDispatcherInterface | None,
        http_client: HttpClientInterface | None,
        logger: LoggerInterface | None,
    ) -> Transport:
        """Return a builder over the installed factories, handing each these collaborators."""
        return cls(
            discovery=TransportFactoryDiscovery(
                event_dispatcher=event_dispatcher, http_client=http_client, logger=logger
            ),
            logger=logger,
        )

    def _build(self, node: DsnNode) -> TransportInterface:
        """Build the transport ``node`` reads as; groups nest a bounded depth."""
        if isinstance(node, str):
            return self.from_dsn_object(Dsn.from_string(node))
        return _group(node, [self._build(member) for member in node.members], self._logger)


def _group(
    group: DsnGroup, members: list[TransportInterface], logger: LoggerInterface | None
) -> TransportInterface:
    """Build the transport ``group``'s keyword names over ``members``, logging to ``logger``.

    The match covers every keyword, which the type checker holds it to.
    """
    kind: type[RoundRobinTransport]
    match group.keyword:
        case "failover":
            kind = FailoverTransport
        case "roundrobin":
            kind = RoundRobinTransport
    if group.retry_period is None:
        return kind(members, logger=logger)
    return kind(members, group.retry_period, logger=logger)
