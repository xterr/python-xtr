"""What ``refunds.json`` must be read as: one event per entry of the batch it carries."""

from __future__ import annotations

from xtr_remote_event import RemoteEvent

EXPECTED = [
    RemoteEvent(
        "order.refunded", "ord_2", {"type": "order.refunded", "id": "ord_2", "amount": 1200}
    ),
    RemoteEvent(
        "order.refunded", "ord_3", {"type": "order.refunded", "id": "ord_3", "amount": 450}
    ),
]
