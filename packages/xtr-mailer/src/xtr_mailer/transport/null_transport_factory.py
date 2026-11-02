"""Builds the null transport from ``null://null``."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_mailer.exception import UnsupportedSchemeError

from .null_transport import NullTransport
from .transport_factory_interface import TransportFactoryInterface

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_client_contracts import HttpClientInterface
    from xtr_logging_contracts import LoggerInterface

    from .dsn import Dsn

__all__ = ["NullTransportFactory"]

_SCHEMES = ("null",)


@final
class NullTransportFactory(TransportFactoryInterface):
    """Builds a :class:`NullTransport` for ``null://``.

    The null transport reaches no server, so this factory needs no HTTP client: it accepts one
    only because every factory is built with the same keywords, and keeps nothing of it.
    ``null://`` therefore works in an application that has no HTTP client at all.
    """

    __slots__ = ("_event_dispatcher", "_logger")

    def __init__(
        self,
        event_dispatcher: EventDispatcherInterface | None = None,
        http_client: HttpClientInterface | None = None,
        logger: LoggerInterface | None = None,
    ) -> None:
        """Build null transports announcing emails on ``event_dispatcher``, logging to ``logger``.

        Args:
            event_dispatcher: Where the transports announce emails; ``None`` announces nothing.
            http_client: Accepted and unused: every factory is built with one.
            logger: Where the transports log; ``None`` logs nothing.
        """
        del http_client
        self._event_dispatcher: EventDispatcherInterface | None = event_dispatcher
        self._logger: LoggerInterface | None = logger

    @override
    def create(self, dsn: Dsn) -> NullTransport:
        """Build a null transport.

        Raises:
            UnsupportedSchemeError: ``dsn``'s scheme is not ``null``.
        """
        if not self.supports(dsn):
            raise UnsupportedSchemeError(dsn.scheme, "null", _SCHEMES)
        return NullTransport(self._event_dispatcher, self._logger)

    @override
    def supports(self, dsn: Dsn) -> bool:
        """Tell whether ``dsn``'s scheme is ``null``."""
        return dsn.scheme in _SCHEMES
