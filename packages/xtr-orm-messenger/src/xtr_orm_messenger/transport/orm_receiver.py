"""The receive half of an ``orm://`` transport."""

from __future__ import annotations

import logging
import secrets
from typing import TYPE_CHECKING, Final, final

from sqlalchemy.exc import DBAPIError
from typing_extensions import override
from xtr_clock import SystemClock
from xtr_messenger import (
    EncodedEnvelope,
    MessageDecodingFailedError,
    ReceivedStamp,
    ReceiverInterface,
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
    """Claims the messages of one queue, and deletes each once it is settled.

    Workers polling one table run into each other's transactions; a conflict
    says nothing about the message, so a poll sits through
    :data:`MAX_RETRIES` of them in a row before it gives up, and a settle
    tries again with a growing pause. A settle whose database went away waits
    up to :data:`RECONNECT_TIMEOUT` seconds for it and tries once more: losing
    an acknowledgement to a database restart would have the message handed
    out, and handled, again.
    """

    __slots__ = ("_clock", "_conflicts", "_connection", "_name", "_serializer")

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
            yield envelope.with_stamps(ReceivedStamp(self._name))

    @override
    async def ack(self, envelope: Envelope) -> None:
        """Delete the message ``envelope`` was received as: it was handled.

        Raises:
            TransportError: When ``envelope`` was not received from this
                transport, or the database refuses the delete.
        """
        await self._settle(self._message_id(envelope), self._connection.ack, "acknowledge")

    @override
    async def reject(self, envelope: Envelope) -> None:
        """Delete the message ``envelope`` was received as: it failed for good.

        Raises:
            TransportError: When ``envelope`` was not received from this
                transport, or the database refuses the delete.
        """
        await self._settle(self._message_id(envelope), self._connection.reject, "reject")

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
