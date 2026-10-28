"""The request limiters the login flow counts its failed attempts under.

A login form is where an anonymous caller may try again and again, so
the flow counts the attempts: the pieces here name the limits a login
counts under — the address it came from, and the account it named —
with the keys derived inside the limiter, from a secret the application
supplies.
"""

from __future__ import annotations

from .default_login_rate_limiter import DefaultLoginRateLimiter

__all__ = [
    "DefaultLoginRateLimiter",
]
