"""The receive half of an ``orm://`` transport."""

from __future__ import annotations

import asyncio
import logging
import secrets
from typing import TYPE_CHECKING, Final, final

from sqlalchemy.exc import DBAPIError
from typing_extensions import override
from xtr_clock import SystemClock
from xtr_messenger import (
    EncodedEnvelope,
    ErrorDetailsStamp,
    MessageDecodingFailedError,
    ReceivedStamp,
    ReceiverInterface,
    RedeliveryStamp,
    TransportMessageIdStamp,
)

from xtr_orm_messenger.exception import TransportError

from ._database_errors import is_retryable
from .orm_received_stamp import OrmReceivedStamp

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from xtr_clock import ClockInterface
    from xtr_messenger import Envelope, SerializerInterface

    from .connection import Connection
    from .stored_message import StoredMessage

__all__ = ["MAX_RETRIES", "RECONNECT_TIMEOUT", "OrmReceiver"]

MAX_RETRIES: Final = 3
"""How many conflicts in a row a poll, or a settle, sits through before it gives up."""

RECONNECT_TIMEOUT: Final = 5
"""Seconds a settle waits for a lost database to come back before it gives up.

Shorter than a process supervisor usually gives a worker to stop.
"""

_FIRST_BACKOFF: Final = 0.1
"""Seconds before a settle that ran into another transaction tries again; doubled each time."""

#: Warnings go through the messenger channel, so an application capturing the
#: standard library's logging sees them beside the rest of the bus's output.
_LOGGER: Final = logging.getLogger("messenger")


@final
class OrmReceiver(ReceiverInterface):
    """Claims the messages of one queue, deleting each once handled and retrying each rejected.

    A rejected message with attempts left is put back in its queue, due
    after ``base_delay_seconds`` doubled for each attempt it already had, its
    attempt count kept in a :class:`~xtr_messenger.RedeliveryStamp` and the
    reason it failed in an :class:`~xtr_messenger.ErrorDetailsStamp`. Once
    its ``max_attempts`` are spent it is moved to the ``failure_queue`` with
    a fresh count, so whoever consumes that queue gets to try it again; a
    message failing for good in the failure queue itself is deleted.

    Workers polling one table run into each other's transactions; a conflict
    says nothing about the message, so a poll sits through
    :data:`MAX_RETRIES` of them in a row before it gives up, and a settle
    tries again with a growing pause. A settle whose database went away waits
    up to :data:`RECONNECT_TIMEOUT` seconds for it and tries once more: losing
    an acknowledgement to a database restart would have the message handed
    out, and handled, again.

    A message is kept alive while it is held: from the moment it is handed
    to the worker until it is settled, its claim is renewed every half of
    ``redeliver_timeout``, so a handler running longer than that is not
    taken for dead and its message handed to another worker under it. A
    renewal the database refuses is logged and tried again at the next one.
    """

    __slots__ = ("_clock", "_conflicts", "_connection", "_held", "_name", "_serializer")

    def __init__(
        self,
        connection: Connection,
        serializer: SerializerInterface,
        name: str,
        clock: ClockInterface | None = None,
    ) -> None:
        """Receive from ``connection`` as the transport ``name``, decoding with ``serializer``."""
        self._connection = connection
        self._serializer = serializer
        self._name = name
        self._clock: ClockInterface = clock if clock is not None else SystemClock()
        self._conflicts = 0
        self._held: dict[str, asyncio.Task[None]] = {}

    @override
    async def get(self) -> AsyncIterator[Envelope]:
        """Yield each message as it falls due, waiting between polls that find none.

        Never runs dry: a worker stops it by cancelling. A message is yielded
        the moment it is claimed, with nothing awaited in between, so a
        cancellation never loses one; and one lost anyway — the process
        killed — is handed out again after ``redeliver_timeout``.

        A message that does not decode can never be handled, so it is
        rejected at once, its reason logged — never its body, which may carry
        anything a producer put in a message.

        Raises:
            TransportError: When the database refuses a poll for any reason
                but a conflict, or for a conflict :data:`MAX_RETRIES` times in
                a row.
        """
        try:
            while True:
                stored = await self._claim()
                if stored is None:
                    await self._connection.wait()
                    continue
                try:
                    envelope = self.decode(stored)
                except MessageDecodingFailedError as error:
                    _LOGGER.warning(
                        "rejecting message %s of the %r transport: it does not decode (%s)",
                        stored.id,
                        self._name,
                        error.reason,
                    )
                    await self._settle(stored.id, self._connection.reject, "reject")
                    continue
                self._hold(stored.id)
                yield envelope.with_stamps(ReceivedStamp(self._name))
        finally:
            for message_id in list(self._held):
                await self._release(message_id)

    @override
    async def ack(self, envelope: Envelope) -> None:
        """Delete the message ``envelope`` was received as: it was handled.

        Raises:
            TransportError: When ``envelope`` was not received from this
                transport, or the database refuses the delete.
        """
        message_id = self._message_id(envelope)
        await self._release(message_id)
        await self._settle(message_id, self._connection.ack, "acknowledge")

    @override
    async def reject(self, envelope: Envelope) -> None:
        """Retry the message ``envelope`` was received as, or move it to the failure queue.

        Raises:
            TransportError: When ``envelope`` was not received from this
                transport, or the database refuses the update.
        """
        message_id = self._message_id(envelope)
        await self._release(message_id)
        options = self._connection.options
        attempt = _attempts_had(envelope)
        failure = envelope.last(ErrorDetailsStamp)
        next_try = envelope.without_stamps(RedeliveryStamp).without_stamps(ErrorDetailsStamp)
        if failure is not None:
            next_try = next_try.with_stamps(failure)
        if self.will_retry(envelope):
            queue = options.queue
            delay_ms = int(options.base_delay_seconds * (1 << (attempt - 1)) * 1000)
            next_try = next_try.with_stamps(RedeliveryStamp(attempt))
        elif options.queue != options.failure_queue:
            queue = options.failure_queue
            delay_ms = 0
        else:
            await self._settle(message_id, self._connection.reject, "reject")
            return
        encoded = self._serializer.encode(next_try)

        async def requeue(row: str) -> None:
            await self._connection.requeue(
                row, queue=queue, body=encoded.body, headers=encoded.headers, delay_ms=delay_ms
            )

        await self._settle(message_id, requeue, "reject")

    def will_retry(self, envelope: Envelope) -> bool:
        """Tell whether rejecting ``envelope`` puts it back in its queue for another attempt."""
        return _attempts_had(envelope) < self._connection.options.max_attempts

    def decode(self, stored: StoredMessage) -> Envelope:
        """Rebuild the envelope ``stored`` keeps, stamped with the row it came from.

        A transport message id the envelope carried from an earlier transport
        is replaced by this row's, so the id it carries is the one that
        settles it here.

        Raises:
            MessageDecodingFailedError: When the row does not decode.
        """
        envelope = self._serializer.decode(
            EncodedEnvelope(body=stored.body, headers=dict(stored.headers))
        )
        return envelope.without_stamps(TransportMessageIdStamp).with_stamps(
            OrmReceivedStamp(stored.id), TransportMessageIdStamp(stored.id)
        )

    async def _claim(self) -> StoredMessage | None:
        """Claim the next message, or return ``None`` for nothing due or a conflict to sit out."""
        try:
            stored = await self._connection.get()
        except DBAPIError as error:
            if not is_retryable(error):
                raise TransportError(self._name, "get messages", str(error.orig)) from error
            self._conflicts += 1
            if self._conflicts >= MAX_RETRIES:
                self._conflicts = 0
                raise TransportError(self._name, "get messages", str(error.orig)) from error
            return None
        self._conflicts = 0
        return stored

    def _hold(self, message_id: str) -> None:
        """Keep the claim on ``message_id`` alive until it is released."""
        # The current context is right: it is the receiver's own, where the worker collects
        # messages, never a unit of work; the renewals are cancelled when the claim is released.
        # ast-grep-ignore: task-without-context
        self._held[message_id] = asyncio.get_running_loop().create_task(
            self._keep_alive(message_id)
        )

    async def _release(self, message_id: str) -> None:
        """Stop keeping ``message_id`` alive, and wait until its renewals stopped."""
        task = self._held.pop(message_id, None)
        if task is None:
            return
        _ = task.cancel()
        _ = await asyncio.gather(task, return_exceptions=True)

    async def _keep_alive(self, message_id: str) -> None:
        """Renew the claim on ``message_id`` every half of ``redeliver_timeout``."""
        every = self._connection.options.redeliver_timeout / 2
        while True:
            await _pause(every)
            try:
                await self._connection.keepalive(message_id)
            except DBAPIError as error:
                _LOGGER.warning(
                    "could not keep message %s of the %r transport alive (%s); trying again",
                    message_id,
                    self._name,
                    type(error.orig).__name__,
                )

    async def _settle(
        self, message_id: str, operation: Callable[[str], Awaitable[None]], action: str
    ) -> None:
        delay = _FIRST_BACKOFF
        retries = 0
        reconnected = False
        while True:
            try:
                await operation(message_id)
            except DBAPIError as error:
                if is_retryable(error) and retries < MAX_RETRIES:
                    retries += 1
                    await self._clock.sleep_async(delay * _jitter())
                    delay *= 2
                    continue
                if not reconnected and error.connection_invalidated and await self._reconnected():
                    reconnected = True
                    continue
                raise TransportError(
                    self._name, f"{action} message {message_id}", str(error.orig)
                ) from error
            return

    async def _reconnected(self) -> bool:
        """Wait up to :data:`RECONNECT_TIMEOUT` seconds for the database to answer again."""
        for _ in range(RECONNECT_TIMEOUT):
            await self._clock.sleep_async(1)
            if await self._connection.ping():
                return True
        return False

    def _message_id(self, envelope: Envelope) -> str:
        stamp = envelope.last(OrmReceivedStamp)
        if stamp is None:
            raise TransportError(
                self._name,
                "settle a message",
                "it carries no OrmReceivedStamp, so it was not received from this transport",
            )
        return stamp.id


def _jitter() -> float:
    """Return a factor within 10% of one, so workers that collided do not collide again."""
    return 1 + (secrets.randbelow(21) - 10) / 100


def _attempts_had(envelope: Envelope) -> int:
    """Return how many attempts ``envelope`` has had, the one just made included."""
    redelivery = envelope.last(RedeliveryStamp)
    return 1 + (redelivery.retry_count if redelivery is not None else 0)


async def _pause(seconds: float) -> None:
    """Wait ``seconds`` of the event loop's own time between two renewals of a claim.

    Paced by the loop, not by the receiver's clock: a renewal runs beside
    whatever handles the message, and a clock that only moves when told —
    a test's — would be moved for every reader by a background wait.
    """
    await asyncio.sleep(seconds)
