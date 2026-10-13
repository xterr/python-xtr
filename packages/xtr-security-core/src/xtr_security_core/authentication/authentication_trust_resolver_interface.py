"""What tells how strongly a token was authenticated."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface

__all__ = ["AuthenticationTrustResolverInterface"]


@runtime_checkable
class AuthenticationTrustResolverInterface(Protocol):
    """Resolves the authentication status of a given token.

    A voter granting ``IS_AUTHENTICATED`` asks only whether anyone is behind
    the token; one granting ``IS_AUTHENTICATED_FULLY`` asks whether they proved
    their credentials rather than being remembered; one granting
    ``IS_AUTHENTICATED_RECENTLY`` asks how long ago they did. This contract
    answers each without any voter having to know how a token was made.
    """

    def is_authenticated(self, token: TokenInterface | None = None) -> bool:
        """Resolve whether ``token`` is authenticated."""
        ...

    def is_remember_me(self, token: TokenInterface | None = None) -> bool:
        """Resolve whether ``token`` is authenticated using remember-me capabilities."""
        ...

    def is_full_fledged(self, token: TokenInterface | None = None) -> bool:
        """Resolve whether ``token`` is fully authenticated."""
        ...

    def is_authenticated_recently(self, token: TokenInterface | None = None) -> bool:
        """Resolve whether the user authenticated recently enough for a sensitive action."""
        ...

    def is_authenticated_very_recently(self, token: TokenInterface | None = None) -> bool:
        """Resolve whether the user authenticated recently enough for the most sensitive actions.

        A stricter bar than :meth:`is_authenticated_recently`.
        """
        ...
