"""The error a session storage failure surfaces as."""

from __future__ import annotations

from .http_foundation_error import HttpFoundationError

__all__ = ["SessionError"]


class SessionError(HttpFoundationError):
    """The storage a session persists through could not do what was asked of it.

    Raised where the failure must be heard — a load that cannot happen, a
    write the backend would not keep, an entry that could not be removed —
    and never where a stranger's input merely reads as nothing: an ID cookie
    nobody can read is treated as no cookie, not as an error.
    """
