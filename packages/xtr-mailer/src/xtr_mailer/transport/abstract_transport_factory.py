"""The base of every transport factory."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_mailer.exception import IncompleteDsnError

from .transport_factory_interface import TransportFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_client_contracts import HttpClientInterface
    from xtr_logging_contracts import LoggerInterface

    from .dsn import Dsn

__all__ = ["AbstractTransportFactory"]


class AbstractTransportFactory(TransportFactoryInterface, ABC):
    """Builds transports for the schemes it lists, handing each the collaborators it was given.

    This constructor is the one a discovered factory is built with — keywords
    ``event_dispatcher``, ``http_client`` and ``logger`` — so a provider library inheriting it
    is found by its DSN scheme with no wiring (see
    :class:`~xtr_mailer.transport.TransportFactoryDiscovery`). A factory whose transports
    reach their provider over HTTP declares ``http_client`` required in a constructor of its
    own: discovery then refuses to build it without a client, naming the scheme, rather than
    building transports that fail on their first email.

    A subclass lists its schemes in :meth:`_get_supported_schemes` and builds the transport in
    :meth:`create`, reading credentials with :meth:`_get_user` and :meth:`_get_password`.
    """

    def __init__(
        self,
        event_dispatcher: EventDispatcherInterface | None = None,
        http_client: HttpClientInterface | None = None,
        logger: LoggerInterface | None = None,
    ) -> None:
        """Build transports that announce on ``event_dispatcher`` and log to ``logger``.

        Args:
            event_dispatcher: Where the transports built announce emails; ``None`` announces
                nothing.
            http_client: What the transports built reach their provider through, for those that
                reach one over HTTP.
            logger: Where the transports built log; ``None`` logs nothing.
        """
        self._event_dispatcher: EventDispatcherInterface | None = event_dispatcher
        self._http_client: HttpClientInterface | None = http_client
        self._logger: LoggerInterface | None = logger

    @override
    def supports(self, dsn: Dsn) -> bool:
        """Tell whether ``dsn``'s scheme is one of :meth:`_get_supported_schemes`, as written."""
        return dsn.scheme in self._get_supported_schemes()

    @abstractmethod
    def _get_supported_schemes(self) -> Sequence[str]:
        """Return the DSN schemes this factory serves."""

    def _get_user(self, dsn: Dsn) -> str:
        """Return the DSN's user — an SMTP user, a provider's key.

        Raises:
            IncompleteDsnError: The DSN carries no user.
        """
        if dsn.user is None:
            raise IncompleteDsnError("User is not set.")
        return dsn.user

    def _get_password(self, dsn: Dsn) -> str:
        """Return the DSN's password.

        Raises:
            IncompleteDsnError: The DSN carries no password.
        """
        if dsn.password is None:
            raise IncompleteDsnError("Password is not set.")
        return dsn.password
