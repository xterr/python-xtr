"""The event that lets listeners resolve and check a passport's badges."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from xtr_security_http.authenticator.authenticator_interface import AuthenticatorInterface
    from xtr_security_http.authenticator.passport.passport import Passport

__all__ = ["CheckPassportEvent"]


@dataclass(frozen=True)
class CheckPassportEvent(Event):
    """Announces that a passport is ready for its badges to be resolved and checked.

    Dispatched once an authenticator has produced a passport, before a token is
    made from it. Listeners resolve the badges the authenticator left for them
    — a user provider sets a
    :class:`~xtr_security_http.authenticator.passport.badge.user_badge.UserBadge`'s
    loader, a credentials listener verifies a password — each marking the badge
    it handled resolved. Every badge must be resolved by the time the listeners
    are done, or authentication fails.

    The event is mutable in spirit: a listener reaches into the passport it
    carries and changes the badges' state. The dataclass itself is frozen — the
    authenticator and passport it names do not change — but stopping it skips
    the listeners that have not run, exactly as any event.

    Attributes:
        authenticator: The authenticator that produced the passport.
        passport: The passport whose badges are to be resolved and checked.
    """

    authenticator: AuthenticatorInterface
    passport: Passport

    def get_authenticator(self) -> AuthenticatorInterface:
        """Return the authenticator that produced the passport."""
        return self.authenticator

    def get_passport(self) -> Passport:
        """Return the passport whose badges are to be resolved and checked."""
        return self.passport
