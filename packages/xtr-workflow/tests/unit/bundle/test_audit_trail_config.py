"""The audit trail is off until enabled."""

from __future__ import annotations

from xtr_workflow.bundle import AuditTrailConfig


def test_the_audit_trail_is_disabled_by_default() -> None:
    assert not AuditTrailConfig().enabled


def test_the_audit_trail_can_be_enabled() -> None:
    assert AuditTrailConfig(enabled=True).enabled
