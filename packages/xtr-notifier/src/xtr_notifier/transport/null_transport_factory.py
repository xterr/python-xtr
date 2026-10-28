"""Builds the null transport from ``null://null``."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_notifier.exception import UnsupportedSchemeError

from .null_transport import NullTransport
from .transport_factory_interface import TransportFactoryInterface

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_client_contracts import HttpClientInterface

    from .dsn import Dsn

__all__ = ["NullTransportFactory"]

_SCHEMES = ("null",)


@final
class NullTransportFactory(TransportFactoryInterface):
    """Builds a :class:`NullTransport` for ``null://`` — chat, SMS and push alike.

    The null transport talks to no provider, so this factory needs no HTTP
    client: it accepts one only because discovery builds every factory with the
    same keywords, and keeps nothing of it. ``null://`` therefore works in an
    application that has no HTTP client at all.
    """

    __slots__ = ("_event_dispatcher",)

    def __init__(
        self,
        http_client: HttpClientInterface | None = None,
        event_dispatcher: EventDispatcherInterface | None = None,
    ) -> None:
        """Build null transports announcing messages on ``event_dispatcher``.

        Args:
            http_client: Accepted and unused: discovery passes one to every factory.
            event_dispatcher: Where the transports announce messages; ``None``
                announces nothing.
        """
        del http_client
        self._event_dispatcher = event_dispatcher

    @override
    def create(self, dsn: Dsn) -> NullTransport:
        """Build a null transport.

        Raises:
            UnsupportedSchemeError: If ``dsn``'s scheme is not ``null``.
        """
        if not self.supports(dsn):
            raise UnsupportedSchemeError(dsn.scheme, "null", _SCHEMES)
        return NullTransport(self._event_dispatcher)

    @override
    def supports(self, dsn: Dsn) -> bool:
        """Tell whether ``dsn``'s scheme is ``null``."""
        return dsn.scheme in _SCHEMES
