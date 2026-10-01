"""How much of an authentication failure a client is allowed to learn."""

from __future__ import annotations

from enum import Enum

__all__ = ["ExposeSecurityLevel"]


class ExposeSecurityLevel(Enum):
    """How much of the real reason an authentication failure may reveal.

    Telling a client precisely why authentication failed helps an attacker:
    that a user exists, or that an account is merely disabled rather than
    unknown, is a way to probe. This level decides how much leaks out; anything
    hidden is reported to the client as plain bad credentials.

    - ``NONE`` — reveal nothing: unknown users and account-status failures
      alike become bad credentials. The safe default.
    - ``ACCOUNT_STATUS`` — reveal that an account is disabled, locked or
      expired, but still hide whether a user exists.
    - ``ALL`` — reveal every failure as it happened. For development.
    """

    NONE = "none"
    ACCOUNT_STATUS = "account_status"
    ALL = "all"
