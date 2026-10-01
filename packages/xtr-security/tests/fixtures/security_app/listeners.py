"""Listeners the served fixture registers to record the security events it sees.

A global listener on the check-passport, login-success and vote events records
them into a process-level log the served tests read, so a test can assert the
order events fired in and that a global listener hears a firewall's own events.
"""

from __future__ import annotations

from xtr_event_dispatcher import as_event_listener
from xtr_security_core.event.vote_event import VoteEvent
from xtr_security_http.event.check_passport_event import CheckPassportEvent
from xtr_security_http.event.login_success_event import LoginSuccessEvent

__all__ = ["EVENTS", "record_check_passport", "record_login_success", "record_vote"]

EVENTS: list[str] = []
"""The names of the security events the listeners recorded, in order."""


@as_event_listener()
def record_check_passport(event: CheckPassportEvent) -> None:
    """Record that a passport was checked."""
    del event
    EVENTS.append("check_passport")


@as_event_listener()
def record_login_success(event: LoginSuccessEvent) -> None:
    """Record a successful login."""
    del event
    EVENTS.append("login_success")


@as_event_listener()
def record_vote(event: VoteEvent) -> None:
    """Record that a voter was traced."""
    del event
    EVENTS.append("vote")
