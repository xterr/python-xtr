"""The handler of ``AuditEvent``: it writes the audit trail."""

from __future__ import annotations

from xtr_dependency_injection import Injected
from xtr_messenger import as_message_handler

from bookshop.message.audit_event import AuditEvent
from bookshop.service.security_audit_trail import SecurityAuditTrail

__all__ = ["record_audit_event"]


@as_message_handler(AuditEvent)
async def record_audit_event(message: AuditEvent, audit: Injected[SecurityAuditTrail]) -> None:
    """Write the audit trail."""
    audit.record(message.subject, message.detail)
