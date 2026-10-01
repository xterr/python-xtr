"""The stateless user provider that rebuilds a user from a token's claims."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_core.user.attributes_based_user_provider_interface import (
    AttributesBasedUserProviderInterface,
)
from xtr_service_contracts import ResetInterface

from .jwt_user import JwtUser

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_security_core.user.user_interface import UserInterface

    from .jwt_user_interface import JwtUserInterface

__all__ = ["JwtUserProvider"]


@final
class JwtUserProvider(AttributesBasedUserProviderInterface, ResetInterface):
    """Builds a user from a token's own claims, keeping no store of its own.

    The provider a stateless firewall names: it takes a user class that can be
    built from a payload, and rebuilds a user from the claims the authenticator
    hands it — no database, no lookup. It caches by identifier for the span of one
    unit of work and clears that cache on reset, so a worker reusing the provider
    across messages never serves a stale user.
    """

    __slots__ = ("_cache", "_user_class")

    def __init__(self, user_class: type[JwtUserInterface] = JwtUser) -> None:
        """Build users of ``user_class`` from the claims of the tokens that name them."""
        self._user_class = user_class
        self._cache: dict[str, UserInterface] = {}

    @override
    async def load_user_by_identifier(
        self,
        identifier: str,
        attributes: Mapping[str, object] | None = None,
    ) -> UserInterface:
        """Build the user ``identifier`` names from the token ``attributes``."""
        cached = self._cache.get(identifier)
        if cached is not None:
            return cached
        payload: Mapping[str, object] = attributes if attributes is not None else {}
        user = self._user_class.create_from_payload(identifier, payload)
        self._cache[identifier] = user
        return user

    @override
    def supports_class(self, user_class: type) -> bool:
        """Tell whether this provider builds users of ``user_class``."""
        return issubclass(user_class, self._user_class) or user_class is self._user_class

    @override
    def reset(self) -> None:
        """Clear the per-unit cache of built users, ending the unit of work."""
        self._cache.clear()
