"""The events raised at the HTTP edge, around a request's authentication.

The passport check, the token created, a user's own interactive login, and
the login having succeeded or failed. Each derives the event contract's
:class:`~xtr_event_dispatcher_contracts.Event`; a subscriber listens to the
event class itself, which the dispatcher derives the event's name from —
except the interactive login and the user switch, which run under the names
they carry.
"""

from __future__ import annotations

from .authentication_token_created_event import AuthenticationTokenCreatedEvent
from .check_passport_event import CheckPassportEvent
from .check_refreshed_user_event import CheckRefreshedUserEvent
from .interactive_login_event import InteractiveLoginEvent
from .login_failure_event import LoginFailureEvent
from .login_success_event import LoginSuccessEvent
from .logout_event import LogoutEvent
from .switch_user_event import SwitchUserEvent
from .token_deauthenticated_event import TokenDeauthenticatedEvent

__all__ = [
    "AuthenticationTokenCreatedEvent",
    "CheckPassportEvent",
    "CheckRefreshedUserEvent",
    "InteractiveLoginEvent",
    "LoginFailureEvent",
    "LoginSuccessEvent",
    "LogoutEvent",
    "SwitchUserEvent",
    "TokenDeauthenticatedEvent",
]
