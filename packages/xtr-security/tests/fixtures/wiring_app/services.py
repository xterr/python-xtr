"""The token handler service the wiring fixture registers."""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_dependency_injection import as_service
from xtr_security_core import InMemoryUser
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_http import UserBadge
from xtr_security_http.access_token.access_token_handler_interface import (
    AccessTokenHandlerInterface,
)
from xtr_security_http.exception import InvalidAccessTokenError

__all__ = ["WiringTokenHandler"]


@final
@as_service
class WiringTokenHandler(AccessTokenHandlerInterface):
    """Validates the wiring fixture's one good token into a scoped user badge."""

    __slots__ = ()

    @override
    async def get_user_badge_from(self, access_token: str) -> UserBadge:
        """Return the badge the good token proves.

        Raises:
            InvalidAccessTokenError: For any token but ``good``.
        """
        if access_token != "good":
            raise InvalidAccessTokenError("The token is not known.")

        def load(identifier: str) -> UserInterface:
            return InMemoryUser(identifier, roles=["ROLE_USER"])

        return UserBadge("alice", user_loader=load, attributes={"scope": ["books:read"]})
