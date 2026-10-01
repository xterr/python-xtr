"""What tells how strongly a token was authenticated."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface

__all__ = ["AuthenticationTrustResolverInterface"]


@runtime_checkable
class AuthenticationTrustResolverInterface(Protocol):
    """Reads the strength of an authentication from a token.

    A voter granting ``IS_AUTHENTICATED`` asks only whether anyone is behind
    the token; one granting ``IS_AUTHENTICATED_FULLY`` asks whether they
    authenticated this unit of work rather than being carried over. This
    contract answers both without any voter having to know how a token was
    made.
    """

    def is_authenticated(self, token: TokenInterface | None) -> bool:
        """Tell whether ``token`` carries an authenticated user at all."""
        ...

    def is_full_fledged(self, token: TokenInterface | None) -> bool:
        """Tell whether ``token`` was fully authenticated this unit of work."""
        ...
