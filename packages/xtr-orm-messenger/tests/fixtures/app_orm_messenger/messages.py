"""What the fixture app queues."""

from __future__ import annotations

from dataclasses import dataclass

from xtr_messenger import as_message


@as_message(name="tests.orm_messenger.app.queued_order.v1")
@dataclass(frozen=True, slots=True)
class QueuedOrder:
    """Routed to the ``orders`` transport: handled only once a worker claims it."""

    order: str
