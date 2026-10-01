"""The names the core security events are dispatched and listened to under.

Each event is keyed by its qualified class name (the repository's convention,
:func:`~xtr_event_dispatcher_contracts.event_name_of`). A subscriber listens to
one of these constants rather than importing the event class only to name it.

Only the core events live here — the success of an authentication, and a
voter's vote. The events raised at the HTTP edge are named by
:mod:`xtr_security_http.security_events`.
"""

from __future__ import annotations

from typing import Final

from xtr_event_dispatcher_contracts import event_name_of

from .event.authentication_success_event import AuthenticationSuccessEvent
from .event.vote_event import VoteEvent

__all__ = [
    "AUTHENTICATION_SUCCESS",
    "VOTE",
]

#: Dispatched once a token has been created for an authenticated user.
AUTHENTICATION_SUCCESS: Final[str] = event_name_of(AuthenticationSuccessEvent)

#: Dispatched by a traceable voter each time the voter it wraps answers.
VOTE: Final[str] = event_name_of(VoteEvent)
