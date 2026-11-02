"""The base of every transport: events around the send, throttling, a rate limiter."""

from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from typing_extensions import override
from xtr_clock import SystemClock
from xtr_logging_contracts import NullLogger

from xtr_mailer.envelope import Envelope
from xtr_mailer.event import FailedMessageEvent, MessageEvent, SentMessageEvent
from xtr_mailer.exception import LogicError
from xtr_mailer.remote_template_email import RemoteTemplateEmail
from xtr_mailer.sent_message import SentMessage

from .remote_template_transport_interface import RemoteTemplateTransportInterface
from .transport_interface import TransportInterface

if TYPE_CHECKING:
    from typing import Self

    from xtr_clock import ClockInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_mime import RawMessage
    from xtr_rate_limiter import LimiterInterface, RateLimiterFactoryInterface

__all__ = ["AbstractTransport"]


class AbstractTransport(TransportInterface, ABC):
    """Sends an email through :meth:`_do_send`, announcing it before and the outcome after.

    :meth:`send` works on a copy of the email and of the envelope — the envelope its headers
    give when none is handed over — so a listener changing either leaves the caller's alone.
    It dispatches a :class:`~xtr_mailer.event.MessageEvent` a listener may reject the email
    on, then a :class:`~xtr_mailer.event.SentMessageEvent`, or a
    :class:`~xtr_mailer.event.FailedMessageEvent` before the error goes on — rendering
    included, since the email is rendered once, for the send, and a listener recording failures
    must hear of one it cannot be rendered for.

    Two caps on the pace, both off until set: :meth:`set_max_per_second` spaces the sends out
    by waiting on the clock after each, and :meth:`set_rate_limiter_factory` refuses an email
    once a limiter has no token left for it.
    """

    def __init__(
        self,
        event_dispatcher: EventDispatcherInterface | None = None,
        logger: LoggerInterface | None = None,
        clock: ClockInterface | None = None,
    ) -> None:
        """Announce each email on ``event_dispatcher``, waiting its turn on ``clock``.

        Args:
            event_dispatcher: Where the email events go; ``None`` announces nothing.
            logger: Where the transport logs; ``None`` logs nothing.
            clock: What the pace set by :meth:`set_max_per_second` is kept on.
        """
        self._event_dispatcher: EventDispatcherInterface | None = event_dispatcher
        self._logger: LoggerInterface = logger if logger is not None else NullLogger()
        self._clock: ClockInterface = clock if clock is not None else SystemClock()
        self._rate: float = 0.0
        self._last_sent: float = 0.0
        self._rate_limiter_factory: RateLimiterFactoryInterface | None = None

    def set_max_per_second(self, rate: float) -> Self:
        """Send at most ``rate`` emails a second; zero or less sends as fast as it can.

        The pace starts afresh: the next email goes at once.
        """
        self._rate = max(rate, 0.0)
        self._last_sent = 0.0
        return self

    def set_rate_limiter_factory(self, rate_limiter_factory: RateLimiterFactoryInterface) -> Self:
        """Take a token from a limiter of ``rate_limiter_factory`` for each email.

        An email no token is left for is not sent: :meth:`send` raises the limiter's
        ``RateLimitExceededError``.
        """
        self._rate_limiter_factory = rate_limiter_factory
        return self

    @override
    async def send(
        self, message: RawMessage, envelope: Envelope | None = None
    ) -> SentMessage | None:
        """Send a copy of ``message``, announced before and after; ``None`` if it was rejected.

        Raises:
            LogicError: ``message`` is raw and no envelope is given, or it is rendered from a
                provider's template this transport cannot send.
            Exception: Whatever rendering, the rate limiter or :meth:`_do_send` raised, once
                it was announced.
        """
        message = copy.copy(message)
        envelope = copy.copy(envelope) if envelope is not None else Envelope.create(message)
        factory = self._rate_limiter_factory
        limiter = None if factory is None else factory.create()
        try:
            return await self._send_announced(message, envelope, limiter)
        finally:
            await self._throttle()

    @abstractmethod
    async def _do_send(self, message: SentMessage) -> None:
        """Hand ``message`` over, recording on it the message id and the transcript learned.

        Raises:
            TransportError: The server cannot be reached or refuses the email.
        """

    @override
    @abstractmethod
    def __str__(self) -> str:
        """Name the transport, without a credential."""

    async def _send_announced(
        self, message: RawMessage, envelope: Envelope, limiter: LimiterInterface | None
    ) -> SentMessage | None:
        dispatcher = self._event_dispatcher
        if dispatcher is None:
            self._ensure_remote_template_support(message)
            return await self._send_limited(SentMessage(message, envelope), limiter)
        event = await dispatcher.dispatch(MessageEvent(message, envelope, str(self)))
        if event.is_rejected():
            return None
        message = event.get_message()
        self._ensure_remote_template_support(message)
        try:
            # Rendered here, inside the try: a message that cannot be rendered is a failure too.
            sent = await self._send_limited(SentMessage(message, event.get_envelope()), limiter)
        except Exception as error:
            _ = await dispatcher.dispatch(FailedMessageEvent(message, error))
            raise
        _ = await dispatcher.dispatch(SentMessageEvent(sent))
        return sent

    async def _send_limited(
        self, sent: SentMessage, limiter: LimiterInterface | None
    ) -> SentMessage:
        if limiter is not None:
            _ = (await limiter.consume(1)).ensure_accepted()
        await self._do_send(sent)
        return sent

    def _ensure_remote_template_support(self, message: RawMessage) -> None:
        if (
            isinstance(message, RemoteTemplateEmail)
            and message.get_remote_template() is not None
            # A marker protocol: only a class deriving from it has it (see its docstring).
            and RemoteTemplateTransportInterface not in type(self).__mro__
        ):
            raise LogicError(
                f'The "{type(self).__name__}" transport does not support sending emails rendered '
                "from a remote template."
            )

    async def _throttle(self) -> None:
        """Wait until the next email is due, at the pace :meth:`set_max_per_second` set."""
        if self._rate == 0:
            return
        wait = 1 / self._rate - (self._clock.now().timestamp() - self._last_sent)
        if wait > 0:
            self._logger.debug(
                'Email transport "{transport}" sleeps for {seconds} seconds.',
                {"transport": str(self), "seconds": round(wait, 2)},
            )
            await self._clock.sleep_async(wait)
        self._last_sent = self._clock.now().timestamp()
