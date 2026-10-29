"""An audit entry: a message routed nowhere and declaring no transport."""

from __future__ import annotations

from dataclasses import dataclass

from xtr_messenger import as_message

__all__ = ["AuditEvent"]


# The wire name it travelled under before it moved here, pinned so it does not change.
@as_message(name="bookshop.messaging.messages:AuditEvent")
@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Something worth an audit trail. Routed nowhere and declaring nothing.

    With ``handle_unrouted=True`` in the dev configuration it is handled in this process;
    with ``require_sender=True`` in prod the routing table's ``"*"`` sends it on.
    """

    subject: str
    detail: str
