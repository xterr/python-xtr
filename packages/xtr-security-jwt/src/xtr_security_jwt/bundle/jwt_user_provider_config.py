"""The user-provider configuration for the stateless JWT user."""

from __future__ import annotations

from dataclasses import dataclass, field

from xtr_security_jwt.security.user.jwt_user import JwtUser

__all__ = ["JwtUserProviderConfig"]


def _default_user_class() -> type:
    """Return the default user class the stateless provider builds."""
    return JwtUser


@dataclass(frozen=True, slots=True)
class JwtUserProviderConfig:
    """A stateless user provider that rebuilds a user from a token's claims.

    A deployment that keeps no user store names one of these, and the bundle
    registers a provider building ``user_class`` from each token's payload.

    Attributes:
        user_class: The class the provider builds from a token's claims; it must
            be buildable from a payload, and defaults to the plain JWT user.
    """

    user_class: type = field(default_factory=_default_user_class)
