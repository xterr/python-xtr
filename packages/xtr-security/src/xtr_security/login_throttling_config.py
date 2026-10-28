"""The login-throttling block a firewall's configuration carries.

A login form is where an anonymous caller may try again and again, so the
flow counts the attempts: the address each came from, and the account each
named — the address's count surviving any one account's success, so one
client may not farm the accounts of a whole directory. The counts are kept
by the rate limiter over the storage the application registered; the secret
the counting keys are derived with is the application's to supply, never
generated.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["LoginThrottlingConfig"]


@dataclass(frozen=True, slots=True)
class LoginThrottlingConfig:
    """How a firewall's logins are counted and refused.

    Attributes:
        secret: The secret the counting keys are derived with — the
            application's to supply, never generated. Checked where it is
            used: the bundle builds and boots without it, and the listener
            fails naming it the first time it is asked for.
        global_limit: How many attempts one client address may make.
        global_interval: How long a window of ``global_limit`` attempts
            lasts — ``"15 minutes"``, ``"1 hour 30 minutes"``, or any span
            the rate limiter reads.
        local_limit: How many attempts one account from one address may
            make.
        local_interval: How long a window of ``local_limit`` attempts lasts.
    """

    secret: str | None = None
    global_limit: int = 5
    global_interval: str = "15 minutes"
    local_limit: int = 5
    local_interval: str = "15 minutes"
