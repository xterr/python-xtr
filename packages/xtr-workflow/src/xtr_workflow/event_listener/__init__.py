"""Listeners for a workflow's events: the audit trail, and the guards set on transitions.

:class:`AuditTrailListener` logs every move a subject makes. A guard is a
callable handed a :class:`GuardContext`, answering whether a transition may
run; :class:`GuardExpression` ties one to the transition it was set on.

The listener running the guards,
:class:`~xtr_workflow.event_listener.guard_listener.GuardListener`, is
imported from its own module and not from here: it needs xtr-security-core,
which only an application using guards installs.
"""

from __future__ import annotations

from .audit_trail_listener import AuditTrailListener
from .guard_context import GuardContext
from .guard_expression import GuardExpression

__all__ = ["AuditTrailListener", "GuardContext", "GuardExpression"]
