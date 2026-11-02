"""The base of every transport: events around the send, throttling, a rate limiter."""

from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_clock import SystemClock
from xtr_logging_contracts import NullLogger

from xtr_mailer._error_text import type_name
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

    A cancelled send — a timeout, a cancel scope, a cancelled task — dispatches neither of the
    last two: the email was neither sent nor refused, and whether it reached the server is
    unknown.

    Two caps on the pace, both off until set: :meth:`set_max_per_second` spaces the sends out
    by waiting on the clock before each, and :meth:`set_rate_limiter_factory` refuses an email
    once a limiter has no token left for it.

    The pace holds however many tasks send at once: each send takes the next free slot, one
    interval after the slot before it, then waits until its slot comes — sends may still overlap
    once started, but never start closer together than the pace allows. An email rejected,
    refused or failing keeps its slot. A send cancelled while it waits gives its slot back when
    no live send holds a later one, together with every slot of a cancelled send just before
    it, so a cancelled burst leaves the transport free from the slot after the last live send;
    a slot ahead of a live send's stays unused, rather than pulling the later ones forward.

    Thread safety: one event loop. The slots are kept with no lock, so every send through one
    transport runs on the same event loop.
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
        self._next_slot: float | None = None
        self._slots: list[_Slot] = []
        self._rate_limiter_factory: RateLimiterFactoryInterface | None = None

    def set_max_per_second(self, rate: float) -> Self:
        """Send at most ``rate`` emails a second; zero or less sends as fast as it can.

        The pace starts afresh: the next email goes at once.
        """
        self._rate = max(rate, 0.0)
        self._next_slot = None
        self._slots = []
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
        await self._wait_for_slot()
        factory = self._rate_limiter_factory
        limiter = None if factory is None else factory.create()
        return await self._send_announced(message, envelope, limiter)

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
                f'The "{type_name(type(self))}" transport does not support sending emails rendered '
                "from a remote template."
            )

    async def _wait_for_slot(self) -> None:
        """Take the next slot at the pace :meth:`set_max_per_second` set, and wait for it.

        Reading the next slot and moving it on — or back, when a cancelled wait gives its slot
        back — happen with no await between them, so no other task sending through this
        transport can take the same slot: on one event loop, that is what a lock would
        guarantee, without one.
        """
        if self._rate == 0:
            return
        now = self._clock.now().timestamp()
        slot = _Slot(now if self._next_slot is None else max(now, self._next_slot))
        self._next_slot = slot.start + 1 / self._rate
        slots = self._slots
        slots.append(slot)
        wait = slot.start - now
        started = False
        try:
            if wait > 0:
                self._logger.debug(
                    'Email transport "{transport}" sleeps for {seconds} seconds.',
                    {"transport": str(self), "seconds": round(wait, 2)},
                )
                await self._clock.sleep_async(wait)
            started = True
        finally:
            if started:
                _started(slots, slot)
            else:
                self._give_back(slots, slot)

    def _give_back(self, slots: list[_Slot], slot: _Slot) -> None:
        """Mark ``slot`` unused, and hand back every unused slot no live send holds one after."""
        slot.cancelled = True
        if slots is not self._slots:  # The pace was set afresh while it waited.
            return
        while slots and slots[-1].cancelled:
            self._next_slot = slots.pop().start


def _started(slots: list[_Slot], slot: _Slot) -> None:
    """Drop the slots before ``slot``: a send started in it, so none of them is handed back."""
    # A send waking late finds its slot dropped by a later one already, and drops nothing.
    del slots[: next((index for index, each in enumerate(slots) if each is slot), 0)]


@final
@dataclass(eq=False, slots=True)
class _Slot:
    """When a send may start, and whether the send waiting for it was cancelled."""

    start: float
    cancelled: bool = False
