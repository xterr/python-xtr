"""Tells how strongly a token was authenticated."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .authentication_trust_resolver_interface import AuthenticationTrustResolverInterface
from .token.null_token import NullToken

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface

__all__ = ["AuthenticationTrustResolver"]


@final
class AuthenticationTrustResolver(AuthenticationTrustResolverInterface):
    """Reads authentication strength from a token.

    A token carries an authenticated user when it is neither absent nor the
    :class:`~xtr_security_core.authentication.token.null_token.NullToken` that
    stands for nobody. Without the remembered-me machinery this library does
    not port, full authentication and authentication are the same question:
    a real token is both, an anonymous one is neither.
    """

    @override
    def is_authenticated(self, token: TokenInterface | None) -> bool:
        """Tell whether ``token`` carries an authenticated user at all."""
        return (
            token is not None and not isinstance(token, NullToken) and token.get_user() is not None
        )

    @override
    def is_full_fledged(self, token: TokenInterface | None) -> bool:
        """Tell whether ``token`` was fully authenticated this unit of work."""
        return self.is_authenticated(token)
