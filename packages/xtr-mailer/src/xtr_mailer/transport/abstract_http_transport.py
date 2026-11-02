"""The base of every transport that hands an email to a provider over HTTP."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from typing_extensions import override
from xtr_http_client_contracts.exception import DecodingError, HttpClientError, HttpError

from xtr_mailer.exception import HttpTransportError, TransportError

from ._http_debug import http_debug
from .abstract_transport import AbstractTransport

if TYPE_CHECKING:
    from typing import Self

    from xtr_clock import ClockInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_client_contracts import HttpClientInterface, HttpResponseInterface
    from xtr_logging_contracts import LoggerInterface

    from xtr_mailer.sent_message import SentMessage

__all__ = ["AbstractHttpTransport"]


class AbstractHttpTransport(AbstractTransport, ABC):
    """Sends an email with the HTTP request :meth:`_do_send_http` makes to a provider.

    The HTTP client is required: the transport never builds one of its own, so the
    application's client — its timeouts, its proxy, its retries — is the one every provider is
    reached through. The host and port a DSN names in place of ``default`` are set with
    :meth:`set_host` and :meth:`set_port`; a subclass reads them as ``_host`` and ``_port``,
    ``None`` meaning its provider's own.

    The exchange is appended to the sent message's debug log — or to the error's, when the
    provider refuses the email — as the request line and each line of the answer, with nothing
    that could be a credential: no user info or query in any URL, the request's or one the
    answer echoes; no value of a header named after a credential (an authorization, an
    authentication challenge, a cookie, a session, a token, a secret, a key); never the
    request's headers.

    No error of the HTTP client goes on as it is. An answer the client raised for — a status
    read with ``throw`` left on — becomes an :class:`~xtr_mailer.exception.HttpTransportError`
    carrying it; an answer that cannot be read, a provider that cannot be reached and a
    transfer that timed out become a :class:`~xtr_mailer.exception.TransportError`, which a
    failover transport takes as the sign to move on. Neither repeats the client's message, which
    names the URL. A cancelled send is cancelled, not failed: nothing is caught for it.

    The message is rendered before the request, as the email's bytes are what most HTTP
    transports post; :class:`~xtr_mailer.transport.AbstractApiTransport` posts fields instead,
    and renders nothing.
    """

    def __init__(
        self,
        http_client: HttpClientInterface,
        event_dispatcher: EventDispatcherInterface | None = None,
        logger: LoggerInterface | None = None,
        clock: ClockInterface | None = None,
    ) -> None:
        """Send through ``http_client``, announcing each email on ``event_dispatcher``.

        Args:
            http_client: What the provider is reached through.
            event_dispatcher: Where the email events go; ``None`` announces nothing.
            logger: Where the transport logs; ``None`` logs nothing.
            clock: What the pace set by :meth:`set_max_per_second` is kept on.
        """
        super().__init__(event_dispatcher, logger, clock)
        self._http_client: HttpClientInterface = http_client
        self._host: str | None = None
        self._port: int | None = None

    def set_host(self, host: str | None) -> Self:
        """Reach the provider at ``host``; ``None`` restores the provider's own."""
        self._host = host
        return self

    def set_port(self, port: int | None) -> Self:
        """Reach the provider on ``port``; ``None`` restores the scheme's default."""
        self._port = port
        return self

    @abstractmethod
    async def _do_send_http(self, message: SentMessage) -> HttpResponseInterface:
        """Make the request handing ``message`` over, and return the provider's answer.

        Set the message id the provider answered with on ``message``.

        Raises:
            HttpTransportError: The provider refused the email.
            xtr_http_client_contracts.exception.HttpClientError: The client failed; it is
                turned into a transport error.
        """

    @override
    async def _do_send(self, message: SentMessage) -> None:
        """Make the request, log the exchange, and turn a client's error into one of ours.

        Ours is raised once the client's is handled, so not even the hidden context of the
        error holds the client's, and the URL it names.

        Raises:
            HttpTransportError: The provider refused the email.
            TransportError: The provider cannot be reached, or its answer cannot be read.
        """
        failure: TransportError
        try:
            response = await self._do_send_http(message)
        except HttpTransportError as error:
            error.append_debug(http_debug(error.response.get_info()))
            raise
        except HttpError as error:
            status = error.response.get_status_code()
            failure = HttpTransportError(
                f'Unable to send an email: the provider of the "{self}" transport answered with '
                f"HTTP {status}.",
                error.response,
                status,
            )
            failure.append_debug(http_debug(error.response.get_info()))
        except DecodingError:
            failure = TransportError(
                f'Unable to send an email: the provider of the "{self}" transport answered with '
                "a body that cannot be read."
            )
        except HttpClientError as error:
            failure = TransportError(
                f'Could not reach the provider of the "{self}" transport '
                f"({type(error).__qualname__})."
            )
        else:
            message.append_debug(http_debug(response.get_info()))
            return
        raise failure
