"""The send half of an ``orm://`` transport."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from sqlalchemy.exc import DBAPIError
from typing_extensions import override
from xtr_messenger import DelayStamp, SenderInterface, TransportMessageIdStamp

from xtr_orm_messenger.exception import TransportError

if TYPE_CHECKING:
    from xtr_messenger import Envelope, SerializerInterface

    from .connection import Connection

__all__ = ["OrmSender"]


@final
class OrmSender(SenderInterface):
    """Writes each envelope it is handed into the table, due after its delay."""

    __slots__ = ("_connection", "_name", "_serializer")

    def __init__(self, connection: Connection, serializer: SerializerInterface, name: str) -> None:
        """Send through ``connection`` as the transport ``name``, encoding with ``serializer``."""
        self._connection = connection
        self._serializer = serializer
        self._name = name

    @override
    async def send(self, envelope: Envelope) -> Envelope:
        """Keep ``envelope``, due after its :class:`~xtr_messenger.DelayStamp`, if any.

        Returns it stamped with the id the row was given.

        Raises:
            MessageEncodingFailedError: When the envelope does not encode.
            TransportError: When the database refuses the insert.
        """
        encoded = self._serializer.encode(envelope)
        delay = envelope.last(DelayStamp)
        try:
            message_id = await self._connection.send(
                encoded.body, encoded.headers, delay.delay_ms if delay is not None else 0
            )
        except DBAPIError as error:
            raise TransportError(self._name, "send a message", str(error.orig)) from error
        return envelope.with_stamps(TransportMessageIdStamp(message_id))
