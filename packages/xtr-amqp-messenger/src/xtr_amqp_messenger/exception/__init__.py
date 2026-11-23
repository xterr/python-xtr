"""Everything this library raises, each one an :class:`AmqpMessengerError`."""

from __future__ import annotations

from .amqp_messenger_error import AmqpMessengerError
from .transport_error import TransportError

__all__ = ["AmqpMessengerError", "TransportError"]
