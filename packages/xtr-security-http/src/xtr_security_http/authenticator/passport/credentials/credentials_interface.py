"""What a set of credentials on a passport answers to."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from xtr_security_http.authenticator.passport.badge.badge_interface import BadgeInterface

__all__ = ["CredentialsInterface"]


@runtime_checkable
class CredentialsInterface(BadgeInterface, Protocol):
    """A credential to verify, carried on a passport as a badge.

    A password to check, a signature to validate. It is a
    :class:`~xtr_security_http.authenticator.passport.badge.badge_interface.BadgeInterface`
    like any other, unresolved until the listener that knows how verifies it —
    at which point it reports resolved and drops whatever secret it held, so a
    credential is consumed exactly once.
    """
