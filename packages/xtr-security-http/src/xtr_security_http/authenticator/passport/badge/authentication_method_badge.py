"""A badge stating which authentication methods an attempt verified."""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

from .badge_interface import BadgeInterface

__all__ = ["AuthenticationMethodBadge"]


@final
class AuthenticationMethodBadge(BadgeInterface):
    """Names the methods an authenticator verified for this attempt.

    An authenticator that proves *how* the caller authenticated — a password,
    a one-time passcode — records each proof here, and the listener that
    collects authentication proofs reads them off the token. The names are
    deduplicated in the order they were given; at least one is required, since
    a badge claiming no method says nothing.
    """

    __slots__ = ("_methods",)

    def __init__(self, *methods: str) -> None:
        """Record the verified methods, deduplicated, keeping their order.

        Args:
            methods: The names of the authentication methods verified.

        Raises:
            InvalidArgumentError: When no method is given.
        """
        if not methods:
            raise InvalidArgumentError("At least one authentication method is required.")
        self._methods: tuple[str, ...] = tuple(dict.fromkeys(methods))

    def get_methods(self) -> tuple[str, ...]:
        """Return the verified methods, deduplicated, in the order given."""
        return self._methods

    @override
    def is_resolved(self) -> bool:
        """Report resolved always: the badge only records what was proven."""
        return True
