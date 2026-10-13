"""A method was called on an object that cannot honour it."""

from __future__ import annotations

from .security_error import SecurityError

__all__ = ["BadMethodCallError"]


class BadMethodCallError(SecurityError):
    """A method was called that this object refuses by design.

    The anonymous token answers every question about itself but accepts no
    user, attribute or authentication proof; the placeholder provider of a
    firewall that has none loads nobody. Calling such a method is a mistake in
    the caller, not a state to recover from.
    """
