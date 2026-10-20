"""The base of every transport that talks to a provider over HTTP."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar, Self

from typing_extensions import override

from xtr_notifier.event import FailedMessageEvent, MessageEvent, SentMessageEvent

from .transport_interface import TransportInterface

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_client_contracts import HttpClientInterface

    from xtr_notifier.message import MessageInterface, SentMessage

__all__ = ["AbstractTransport"]


class AbstractTransport(TransportInterface, ABC):
    """Sends to a provider's HTTP API, announcing each message around the send.

    A subclass implements :meth:`_do_send`, :meth:`supports` and ``__str__``,
    and sets :attr:`HOST` to the provider's API host. :meth:`send` dispatches a
    :class:`~xtr_notifier.event.MessageEvent` before the send, then a
    :class:`~xtr_notifier.event.SentMessageEvent` — or a
    :class:`~xtr_notifier.event.FailedMessageEvent` before the error goes on.

    The HTTP client is required: the transport never builds one of its own, so
    the application's client — its timeouts, its proxy, its retries — is the
    one every provider is reached through. A transport that talks to no
    provider, such as :class:`~xtr_notifier.transport.null_transport.NullTransport`,
    implements :class:`TransportInterface` directly instead.

    The host, port and scheme can be overridden after it is built — what a DSN
    naming a host other than ``default`` does — for a self-hosted provider or a
    test server.
    """

    #: The provider's API host, used unless :meth:`set_host` names another.
    HOST: ClassVar[str] = "localhost"
    #: Whether the provider is reached over HTTPS unless :meth:`set_ssl` says otherwise.
    SSL: ClassVar[bool] = True

    def __init__(
        self,
        http_client: HttpClientInterface,
        event_dispatcher: EventDispatcherInterface | None = None,
    ) -> None:
        """Send through ``http_client``, announcing each message on ``event_dispatcher``.

        Args:
            http_client: What the provider is reached through.
            event_dispatcher: Where the message events go; ``None`` announces nothing.
        """
        self._http_client: HttpClientInterface = http_client
        self._event_dispatcher: EventDispatcherInterface | None = event_dispatcher
        self._host: str | None = None
        self._port: int | None = None
        self._ssl: bool | None = None

    def set_host(self, host: str | None) -> Self:
        """Reach the provider at ``host``; ``None`` restores :attr:`HOST`."""
        self._host = host
        return self

    def set_port(self, port: int | None) -> Self:
        """Reach the provider on ``port``; ``None`` restores the scheme's default."""
        self._port = port
        return self

    def set_ssl(self, ssl: bool | None) -> Self:
        """Reach the provider over HTTPS or not; ``None`` restores :attr:`SSL`."""
        self._ssl = ssl
        return self

    @override
    async def send(self, message: MessageInterface) -> SentMessage:
        """Send ``message``, announcing it before and the outcome after.

        Raises:
            Exception: Whatever :meth:`_do_send` raised, once it was announced.
        """
        if self._event_dispatcher is None:
            return await self._do_send(message)
        _ = await self._event_dispatcher.dispatch(MessageEvent(message))
        try:
            sent = await self._do_send(message)
        except Exception as error:
            _ = await self._event_dispatcher.dispatch(FailedMessageEvent(message, error))
            raise
        _ = await self._event_dispatcher.dispatch(SentMessageEvent(sent))
        return sent

    @abstractmethod
    async def _do_send(self, message: MessageInterface) -> SentMessage:
        """Send ``message`` to the provider and report what it answered.

        Raises:
            TransportError: When the provider cannot be reached or refuses the message.
            UnsupportedMessageTypeError: When ``message`` is not one this transport sends.
        """

    @override
    @abstractmethod
    def __str__(self) -> str:
        """Name the transport, without a credential."""

    def _get_endpoint(self) -> str:
        """Return the host to reach, with the port when one is set."""
        host = self._host or self._get_default_host()
        return f"{host}:{self._port}" if self._port else host

    def _get_default_host(self) -> str:
        """Return the host reached unless one is set; :attr:`HOST` unless overridden."""
        return self.HOST

    def _get_http_scheme(self) -> str:
        """Return ``https`` or ``http``, as the transport is set to reach the provider."""
        return "https" if (self.SSL if self._ssl is None else self._ssl) else "http"
