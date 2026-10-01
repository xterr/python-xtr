"""The names the HTTP-edge security events are dispatched and listened to under.

Each event is keyed by its qualified class name (the repository's convention,
:func:`~xtr_event_dispatcher_contracts.event_name_of`). A subscriber listens to
one of these constants rather than importing the event class only to name it.

These are the events raised around a request's authentication — the passport
check, the token created, and the login having succeeded or failed. The core
events (the success of an authentication, and a vote) are named by
:mod:`xtr_security_core.authentication_events`.
"""

from __future__ import annotations

from typing import Final

from xtr_event_dispatcher_contracts import event_name_of

from .event.authentication_token_created_event import AuthenticationTokenCreatedEvent
from .event.check_passport_event import CheckPassportEvent
from .event.login_failure_event import LoginFailureEvent
from .event.login_success_event import LoginSuccessEvent

__all__ = [
    "AUTHENTICATION_TOKEN_CREATED",
    "CHECK_PASSPORT",
    "LOGIN_FAILURE",
    "LOGIN_SUCCESS",
]

#: Dispatched after an authenticator produced a passport, to resolve its badges.
CHECK_PASSPORT: Final[str] = event_name_of(CheckPassportEvent)

#: Dispatched once a token was created from a passport; a listener may replace it.
AUTHENTICATION_TOKEN_CREATED: Final[str] = event_name_of(AuthenticationTokenCreatedEvent)

#: Dispatched after a token is stored and the success handler ran.
LOGIN_SUCCESS: Final[str] = event_name_of(LoginSuccessEvent)

#: Dispatched when authentication failed; a listener may set the response.
LOGIN_FAILURE: Final[str] = event_name_of(LoginFailureEvent)
