"""One message as the table keeps it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

__all__ = ["StoredMessage"]


@final
@dataclass(frozen=True, slots=True)
class StoredMessage:
    """One row of the messages table, its envelope still encoded.

    Attributes:
        id: The row's identifier, as the transport hands it out.
        body: The encoded message.
        headers: The encoded envelope's headers: its type and its stamps.
        queue: The queue it was sent to.
        created_at: When it was sent, in UTC.
        available_at: When it falls due, in UTC — later than ``created_at``
            for a delayed message.
        delivered_at: When a worker was last handed it, in UTC, or ``None``
            while no worker has been.
    """

    id: str
    body: str
    headers: Mapping[str, str]
    queue: str
    created_at: datetime
    available_at: datetime
    delivered_at: datetime | None
