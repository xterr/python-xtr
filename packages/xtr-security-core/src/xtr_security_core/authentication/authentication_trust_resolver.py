"""The default implementation of the authentication trust resolver."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override
from xtr_clock import SystemClock

from .authentication_trust_resolver_interface import AuthenticationTrustResolverInterface

if TYPE_CHECKING:
    from xtr_clock import ClockInterface

    from xtr_security_core.authentication.token.token_interface import TokenInterface

__all__ = ["AuthenticationTrustResolver"]


class AuthenticationTrustResolver(AuthenticationTrustResolverInterface):
    """Reads authentication strength from a token.

    A token is authenticated when it carries a user, and fully authenticated
    when it is also not a remembered one. The base resolver recognizes no
    remembered token of its own, so :meth:`is_remember_me` is false here and
    every authenticated token is fully authenticated; a resolver that knows a
    remembered token overrides it.

    Recency is answered on time alone, counted from whichever method was proven
    last in the token's authentication proofs.

    Args:
        recent_lifetime: Seconds during which an authentication counts as recent.
        very_recent_lifetime: Seconds during which it counts as very recent.
        clock: The clock reading the current time; the system clock when ``None``.
    """

    __slots__: tuple[str, ...] = ("_clock", "_recent_lifetime", "_very_recent_lifetime")

    _recent_lifetime: int
    _very_recent_lifetime: int
    _clock: ClockInterface

    def __init__(
        self,
        recent_lifetime: int = 2 * 3600,
        very_recent_lifetime: int = 5 * 60,
        clock: ClockInterface | None = None,
    ) -> None:
        """Record the two recency windows and the clock that measures them."""
        self._recent_lifetime = recent_lifetime
        self._very_recent_lifetime = very_recent_lifetime
        self._clock = clock if clock is not None else SystemClock()

    @override
    def is_authenticated(self, token: TokenInterface | None = None) -> bool:
        """Tell whether ``token`` carries a user."""
        return token is not None and token.get_user() is not None

    @override
    def is_remember_me(self, token: TokenInterface | None = None) -> bool:
        """Tell whether ``token`` was remembered; never, as no remembered token exists here."""
        del token
        return False

    @override
    def is_full_fledged(self, token: TokenInterface | None = None) -> bool:
        """Tell whether ``token`` is authenticated and not merely remembered."""
        return self.is_authenticated(token) and not self.is_remember_me(token)

    @override
    def is_authenticated_recently(self, token: TokenInterface | None = None) -> bool:
        """Tell whether the last authentication proof is within the recent window.

        The default answers on time alone. An application that wants a stricter
        policy — a second factor, a password entered minutes ago — overrides
        this method rather than the attribute it answers, and reads the same
        proofs to do so. It repeats the :meth:`is_full_fledged` check the voter
        already enforces, because it is also callable on its own.
        """
        return self._is_authenticated_within(token, self._recent_lifetime)

    @override
    def is_authenticated_very_recently(self, token: TokenInterface | None = None) -> bool:
        """Tell whether the last authentication proof is within the very-recent window.

        The bar for a step that must follow a fresh proof of the credentials,
        such as changing the password; an override is where "very recently"
        can mean a stronger proof rather than a shorter time.
        """
        return self._is_authenticated_within(token, self._very_recent_lifetime)

    def _is_authenticated_within(self, token: TokenInterface | None, lifetime: int) -> bool:
        """Tell whether ``token`` is fully authenticated and was proven within ``lifetime``."""
        if token is None or not self.is_full_fledged(token):
            return False
        proofs = token.get_authentication_proofs()
        if not proofs:
            return False
        return int(self._clock.now().timestamp()) - max(proofs.values()) <= lifetime
