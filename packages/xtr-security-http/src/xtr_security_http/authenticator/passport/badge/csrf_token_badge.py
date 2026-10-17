"""A badge asking that a request's CSRF token be checked."""

from __future__ import annotations

from typing import final

from typing_extensions import override

from .badge_interface import BadgeInterface

__all__ = ["CsrfTokenBadge"]


@final
class CsrfTokenBadge(BadgeInterface):
    """Carries the CSRF token a request presented, for the listener that checks it.

    An authenticator whose form carries a CSRF token adds this badge with the
    token's identifier — a different one per authenticator — and the value the
    request presented. The listener that protects against cross-site request
    forgery compares the two and marks the badge resolved; until then the
    passport check fails, so a request that skipped the check cannot
    authenticate.
    """

    __slots__ = ("_csrf_token", "_csrf_token_id", "_resolved")

    def __init__(self, csrf_token_id: str, csrf_token: str | None) -> None:
        """Record the token's identifier and the value the request presented.

        Args:
            csrf_token_id: An arbitrary string the token is generated under;
                a different one per authenticator improves the token's security.
            csrf_token: The token value the request presented, or ``None`` when
                the request carried none.
        """
        self._csrf_token_id = csrf_token_id
        self._csrf_token = csrf_token
        self._resolved = False

    def get_csrf_token_id(self) -> str:
        """Return the identifier the token is generated under."""
        return self._csrf_token_id

    def get_csrf_token(self) -> str | None:
        """Return the token value the request presented, or ``None``."""
        return self._csrf_token

    def mark_resolved(self) -> None:
        """Mark the token checked.

        Called only by the listener that verified the token against the
        request; nothing else settles this badge.
        """
        self._resolved = True

    @override
    def is_resolved(self) -> bool:
        """Tell whether the token has been checked."""
        return self._resolved
