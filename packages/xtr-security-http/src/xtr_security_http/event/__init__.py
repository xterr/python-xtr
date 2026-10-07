"""The events raised at the HTTP edge, around a request's authentication.

The passport check, the token created, and the login having succeeded or
failed. Each derives the event contract's :class:`~xtr_event_dispatcher_contracts.Event`;
a subscriber listens to the event class itself, which the dispatcher derives the
event's name from.
"""

from __future__ import annotations

from .authentication_token_created_event import AuthenticationTokenCreatedEvent
from .check_passport_event import CheckPassportEvent
from .login_failure_event import LoginFailureEvent
from .login_success_event import LoginSuccessEvent

__all__ = [
    "AuthenticationTokenCreatedEvent",
    "CheckPassportEvent",
    "LoginFailureEvent",
    "LoginSuccessEvent",
]
