"""The base of every provider's transport factory."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_notifier.exception import IncompleteDsnError

from .transport_factory_interface import TransportFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_client_contracts import HttpClientInterface

    from .dsn import Dsn

__all__ = ["AbstractTransportFactory"]


class AbstractTransportFactory(TransportFactoryInterface, ABC):
    """Builds a provider's transports, handing each the HTTP client and the event dispatcher.

    This constructor is the one a discovered factory is built with — keywords
    ``http_client`` and ``event_dispatcher`` — so a provider library that
    inherits it is found by its DSN scheme with no wiring (see
    :class:`~xtr_notifier.transport.transport_factory_discovery.TransportFactoryDiscovery`).
    A subclass lists its schemes in :meth:`_get_supported_schemes` and builds
    the transport in :meth:`create`, reading credentials with :meth:`_get_user`
    and :meth:`_get_password`.
    """

    def __init__(
        self,
        http_client: HttpClientInterface,
        event_dispatcher: EventDispatcherInterface | None = None,
    ) -> None:
        """Build transports reaching their provider through ``http_client``.

        Args:
            http_client: What every transport built reaches its provider through.
            event_dispatcher: Where those transports announce messages; ``None``
                announces nothing.
        """
        self._http_client: HttpClientInterface = http_client
        self._event_dispatcher: EventDispatcherInterface | None = event_dispatcher

    @override
    def supports(self, dsn: Dsn) -> bool:
        """Tell whether ``dsn``'s scheme is one of :meth:`_get_supported_schemes`."""
        return dsn.scheme in self._get_supported_schemes()

    @abstractmethod
    def _get_supported_schemes(self) -> Sequence[str]:
        """Return the DSN schemes this factory serves."""

    def _get_user(self, dsn: Dsn) -> str:
        """Return the DSN's user — usually the provider's token.

        Raises:
            IncompleteDsnError: If the DSN carries no user.
        """
        if dsn.user is None:
            raise IncompleteDsnError("User is not set.", _shown(dsn))
        return dsn.user

    def _get_password(self, dsn: Dsn) -> str:
        """Return the DSN's password.

        Raises:
            IncompleteDsnError: If the DSN carries no password. The error names
                the DSN without its credentials.
        """
        if dsn.password is None:
            raise IncompleteDsnError("Password is not set.", _shown(dsn))
        return dsn.password

    def _get_ssl(self, dsn: Dsn) -> bool | None:
        """Return the ``ssl`` option, or ``None`` to keep the transport's default.

        Raises:
            InvalidArgumentError: If the option is set to something not a boolean.
        """
        return None if dsn.get_option("ssl") is None else dsn.get_boolean_option("ssl")


def _shown(dsn: Dsn) -> str:
    """Return the part of ``dsn`` an error may show: scheme and host, no credentials."""
    return f"{dsn.scheme}://{dsn.host}"
