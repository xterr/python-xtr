"""What ``order_paid.json`` must be read as: one event."""

from __future__ import annotations

from xtr_remote_event import RemoteEvent

EXPECTED = RemoteEvent("order.paid", "ord_1", {"type": "order.paid", "id": "ord_1", "amount": 1200})
