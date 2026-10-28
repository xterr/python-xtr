"""A provider the application wires itself: ``fake://<name>``, recording what it sends.

Defined in the application so the notifier bundle's autoconfiguration finds it, as an
application's own factory would be found: it serves both the chatter and the texter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_http_client import MockResponse

from xtr_notifier.exception import TransportError, UnsupportedSchemeError
from xtr_notifier.message import SentMessage
from xtr_notifier.transport import AbstractTransport, AbstractTransportFactory

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_client_contracts import HttpClientInterface

    from xtr_notifier.message import MessageInterface
    from xtr_notifier.transport import Dsn

__all__ = ["DOWN", "SENT", "RecordingTransport", "RecordingTransportFactory"]

SENT: Final[list[tuple[str, MessageInterface]]] = []
"""Every message a recording transport sent, with the transport's name."""

DOWN: Final = "down"
"""The name of a recording transport that fails every send."""


@final
class RecordingTransport(AbstractTransport):
    """Records each message under its name; the one named :data:`DOWN` fails instead."""

    def __init__(
        self,
        name: str,
        http_client: HttpClientInterface,
        event_dispatcher: EventDispatcherInterface | None,
    ) -> None:
        super().__init__(http_client, event_dispatcher)
        self._name = name

    @override
    def __str__(self) -> str:
        return f"fake://{self._name}"

    @override
    def supports(self, message: MessageInterface) -> bool:
        return True

    @override
    async def _do_send(self, message: MessageInterface) -> SentMessage:
        if self._name == DOWN:
            raise TransportError("down", MockResponse())
        SENT.append((self._name, message))
        return SentMessage(message, str(self))


@final
class RecordingTransportFactory(AbstractTransportFactory):
    """Serves ``fake://<name>``."""

    @override
    def create(self, dsn: Dsn) -> RecordingTransport:
        if not self.supports(dsn):
            raise UnsupportedSchemeError(dsn.scheme, "fake", self._get_supported_schemes())
        return RecordingTransport(dsn.host, self._http_client, self._event_dispatcher)

    @override
    def _get_supported_schemes(self) -> Sequence[str]:
        return ("fake",)
