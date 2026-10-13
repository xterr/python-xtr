"""The names the authentication events are dispatched under."""

from __future__ import annotations

from typing import Final, final

from xtr_event_dispatcher_contracts import event_name_of

from .event.authentication_success_event import AuthenticationSuccessEvent

__all__ = ["AuthenticationEvents"]


@final
class AuthenticationEvents:
    """One name per authentication event, for listeners registered by name.

    An event is keyed by the qualified name of its class, so a listener declared
    on a typed parameter and one registered under the matching constant here are
    registered for the same event. The constants serve where a class cannot be
    written — a listener whose event is chosen at runtime, a subscriber mapping
    names to methods.
    """

    AUTHENTICATION_SUCCESS: Final[str] = event_name_of(AuthenticationSuccessEvent)
    """A user was authenticated by one authenticator."""
