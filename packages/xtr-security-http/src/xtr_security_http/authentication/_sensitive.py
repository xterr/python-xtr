"""Deciding which authentication failures to hide, and hiding them.

Some failures name a fact worth hiding: that a user exists, or that an account
is only disabled. Whether such a failure reaches the client as itself or as a
plain rejection is set by an :class:`ExposeSecurityLevel`. These two helpers
are the whole of that rule — one reads it, the other applies it — and they are
private to the package: callers reach them through the re-exports on
:mod:`xtr_security_http.authentication`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_security_core.exception import (
    AccountStatusError,
    BadCredentialsError,
    CustomUserMessageAccountStatusError,
    UserNotFoundError,
)

from .expose_security_level import ExposeSecurityLevel

if TYPE_CHECKING:
    from xtr_security_core.exception import AuthenticationError

__all__ = ["is_sensitive", "mask"]


def is_sensitive(error: AuthenticationError, level: ExposeSecurityLevel) -> bool:
    """Tell whether ``error`` should be hidden from the client at ``level``.

    An account-status failure that carries its own client-facing message is
    never sensitive: it was raised to be shown. Otherwise, at ``ALL`` nothing
    is hidden; at ``ACCOUNT_STATUS`` a disabled or locked account is revealed
    but an unknown user is not; at ``NONE`` both are hidden.
    """
    if isinstance(error, CustomUserMessageAccountStatusError):
        return False
    if level is ExposeSecurityLevel.ALL:
        return False
    if isinstance(error, AccountStatusError):
        return level is ExposeSecurityLevel.NONE
    return isinstance(error, UserNotFoundError)


def mask(error: AuthenticationError, level: ExposeSecurityLevel) -> AuthenticationError:
    """Return ``error``, or a bad-credentials error hiding it, at ``level``.

    A hidden failure becomes a
    :class:`~xtr_security_core.exception.BadCredentialsError` chained to the real
    one, so the client learns only that its credentials failed while the cause
    survives on ``__cause__`` for the log.
    """
    if not is_sensitive(error, level):
        return error
    masked = BadCredentialsError()
    masked.__cause__ = error
    masked.__suppress_context__ = True
    return masked
