"""The user-provider configuration for the stateless JWT user."""

from __future__ import annotations

from dataclasses import dataclass, field

from xtr_security_core.exception import InvalidArgumentError

from xtr_security_jwt.security.user.jwt_user import JwtUser
from xtr_security_jwt.security.user.jwt_user_interface import JwtUserInterface

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

    def __post_init__(self) -> None:
        """Refuse a user class that cannot be rebuilt from a token's claims.

        Anything that is not a class is named here rather than reaching
        ``issubclass``, which would raise a ``TypeError`` of its own.

        Raises:
            InvalidArgumentError: When ``user_class`` is not a
                :class:`JwtUserInterface` class.
        """
        # The annotation says class; an application writing a configuration is
        # not held to it, and this is where that is caught.
        if not isinstance(self.user_class, type) or not issubclass(  # pyright: ignore[reportUnnecessaryIsInstance]
            self.user_class,
            JwtUserInterface,
        ):
            raise InvalidArgumentError(
                "The JWT user class must implement JwtUserInterface, with a "
                "create_from_payload classmethod.",
            )
