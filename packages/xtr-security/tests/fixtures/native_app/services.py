"""The services the native-params fixture registers: a bearer token handler."""

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

__all__ = ["NativeTokenHandler"]

_USERS = {
    "good": ("alice", ["ROLE_USER"], ["books:read"]),
    "admin": ("root", ["ROLE_USER", "ROLE_ADMIN"], ["books:read", "reports:write"]),
}


@final
@as_service
class NativeTokenHandler(AccessTokenHandlerInterface):
    """Validates the fixture's bearer tokens into a user badge with scopes."""

    __slots__ = ()

    @override
    async def get_user_badge_from(self, access_token: str) -> UserBadge:
        """Return the badge a known token proves, or reject an unknown one.

        Raises:
            InvalidAccessTokenError: When the token is not one the fixture knows.
        """
        known = _USERS.get(access_token)
        if known is None:
            raise InvalidAccessTokenError("The token is not known.")
        identifier, roles, scopes = known

        def load(loaded: str) -> UserInterface:
            return InMemoryUser(loaded, roles=roles)

        return UserBadge(identifier, user_loader=load, attributes={"scope": scopes})
