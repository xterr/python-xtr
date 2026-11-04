"""A provider-like factory serving ``dummy://``, built only with an HTTP client."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from tests.support.dummy_transport import DummyTransport
from xtr_mailer.transport import AbstractTransportFactory

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_client_contracts import HttpClientInterface
    from xtr_logging_contracts import LoggerInterface

    from xtr_mailer.transport import Dsn

__all__ = ["DummyTransportFactory"]


@final
class DummyTransportFactory(AbstractTransportFactory):
    """Builds a :class:`DummyTransport` for the DSN's host; needs a client, as a provider does."""

    def __init__(
        self,
        event_dispatcher: EventDispatcherInterface | None = None,
        *,
        http_client: HttpClientInterface,
        logger: LoggerInterface | None = None,
    ) -> None:
        super().__init__(event_dispatcher, http_client, logger)

    @override
    def create(self, dsn: Dsn) -> DummyTransport:
        return DummyTransport(dsn.host)

    @override
    def _get_supported_schemes(self) -> Sequence[str]:
        return ("dummy",)
