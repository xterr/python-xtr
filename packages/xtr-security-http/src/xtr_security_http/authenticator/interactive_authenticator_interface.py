"""What marks an authenticator as one a user actively logs in through."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["InteractiveAuthenticatorInterface"]


@runtime_checkable
class InteractiveAuthenticatorInterface(Protocol):
    """An authenticator a user actively logs in through.

    A user performs the login themselves — a form submitted, a login link
    followed — as opposed to a session or a bearer token re-establishing the
    same user passively. The manager asks :meth:`is_interactive` once a login
    through this authenticator succeeded; one that reports itself interactive
    announces the login through an
    :class:`~xtr_security_http.event.interactive_login_event.InteractiveLoginEvent`,
    under
    :attr:`~xtr_security_http.security_events.SecurityEvents.INTERACTIVE_LOGIN`,
    so a listener hears the user's own act wherever the credential came from.
    """

    def is_interactive(self) -> bool:
        """Tell whether a login through this authenticator is the user's own act.

        ``True`` has the manager announce the login through the
        interactive-login event; ``False``, or not implementing this
        interface, leaves the login unannounced.
        """
        ...
