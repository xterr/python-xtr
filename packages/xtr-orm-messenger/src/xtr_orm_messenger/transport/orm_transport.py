"""Both halves of an ``orm://`` transport, and what can be asked of its table."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from sqlalchemy.exc import DBAPIError
from typing_extensions import override
from xtr_messenger import TransportInterface

from xtr_orm_messenger.exception import TransportError

from .orm_received_stamp import OrmReceivedStamp
from .orm_receiver import OrmReceiver
from .orm_sender import OrmSender

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_clock import ClockInterface
    from xtr_messenger import Envelope, SerializerInterface

    from .connection import Connection

__all__ = ["OrmTransport"]


@final
class OrmTransport(TransportInterface):
    """Sends to, receives from and lists one queue of a messages table.

    Beyond sending and receiving, the queue can be looked into — counted,
    listed, one message found by id — and a message a long handler holds can
    be kept from being handed out again.
    """

    __slots__ = ("_connection", "_name", "_receiver", "_sender")

    def __init__(
        self,
        connection: Connection,
        serializer: SerializerInterface,
        *,
        name: str = "orm",
        clock: ClockInterface | None = None,
    ) -> None:
        """Use ``connection`` as the transport ``name``.

        Both halves encode and decode with ``serializer``, so a producer and a
        worker built from the same configuration always agree on the wire
        format.
        """
        self._connection = connection
        self._name = name
        self._receiver = OrmReceiver(connection, serializer, name, clock)
        self._sender = OrmSender(connection, serializer, name)

    @property
    def name(self) -> str:
        """The transport's name, which every envelope it receives is stamped with."""
        return self._name

    @property
    def connection(self) -> Connection:
        """What runs this transport's statements."""
        return self._connection

    @override
    async def send(self, envelope: Envelope) -> Envelope:
        """Keep ``envelope`` until a worker claims it; see :meth:`OrmSender.send`."""
        return await self._sender.send(envelope)

    @override
    def get(self) -> AsyncIterator[Envelope]:
        """Yield each message as it falls due; see :meth:`OrmReceiver.get`."""
        return self._receiver.get()

    @override
    async def ack(self, envelope: Envelope) -> None:
        """Delete the message ``envelope`` was received as: it was handled."""
        await self._receiver.ack(envelope)

    @override
    async def reject(self, envelope: Envelope) -> None:
        """Delete the message ``envelope`` was received as: it failed for good."""
        await self._receiver.reject(envelope)

    async def keepalive(self, envelope: Envelope, seconds: int | None = None) -> None:
        """Keep the message ``envelope`` was received as from being handed out again.

        Restarts its redelivery clock: call it while a handler runs longer
        than ``redeliver_timeout``. ``seconds`` is how long the caller means to
        wait before calling again, refused when longer than the timeout, which
        would hand the message out in between.

        Raises:
            TransportError: When ``seconds`` is longer than
                ``redeliver_timeout``, ``envelope`` was not received from this
                transport, or the database refuses the update.
        """
        timeout = self._connection.options.redeliver_timeout
        if seconds is not None and seconds > timeout:
            raise TransportError(
                self._name,
                "keep a message alive",
                f"{seconds} seconds is longer than its redeliver_timeout of {timeout}",
            )
        stamp = envelope.last(OrmReceivedStamp)
        if stamp is None:
            raise TransportError(
                self._name,
                "keep a message alive",
                "it carries no OrmReceivedStamp, so it was not received from this transport",
            )
        try:
            await self._connection.keepalive(stamp.id)
        except DBAPIError as error:
            raise TransportError(self._name, "keep a message alive", str(error.orig)) from error

    async def find(self, message_id: str) -> Envelope | None:
        """Return the envelope kept as ``message_id`` in this queue, or ``None``.

        Raises:
            MessageDecodingFailedError: When the row does not decode.
            TransportError: When the database refuses the query.
        """
        try:
            stored = await self._connection.find(message_id)
        except DBAPIError as error:
            raise TransportError(self._name, "find a message", str(error.orig)) from error
        return None if stored is None else self._receiver.decode(stored)

    async def all(self, limit: int | None = None) -> AsyncIterator[Envelope]:
        """Yield the envelopes a worker could claim now, oldest first, ``limit`` at most.

        Raises:
            MessageDecodingFailedError: When a row does not decode.
            TransportError: When the database refuses the query.
        """
        try:
            async for stored in self._connection.all(limit):
                yield self._receiver.decode(stored)
        except DBAPIError as error:
            raise TransportError(self._name, "list messages", str(error.orig)) from error

    async def count(self) -> int:
        """Return how many messages a worker could claim now.

        Raises:
            TransportError: When the database refuses the query.
        """
        try:
            return await self._connection.count()
        except DBAPIError as error:
            raise TransportError(self._name, "count messages", str(error.orig)) from error

    async def setup(self) -> None:
        """Create the messages table if it does not exist.

        Raises:
            TransportError: When the database refuses to create it.
        """
        try:
            await self._connection.setup()
        except DBAPIError as error:
            raise TransportError(self._name, "create its table", str(error.orig)) from error

    async def close(self) -> None:
        """Release the connection a worker listens for notifications on, if any."""
        await self._connection.close()
