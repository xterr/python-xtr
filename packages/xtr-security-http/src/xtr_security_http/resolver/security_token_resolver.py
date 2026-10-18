"""The service that reads the authenticated token out of the request's storage."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_core.authentication.token.storage.token_storage_interface import (  # noqa: TC002 -- the container reads this constructor parameter's type at runtime
    TokenStorageInterface,
)
from xtr_security_core.exception import AuthenticationCredentialsNotFoundError

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from xtr_security_http.decorator.current_token import CurrentToken

__all__ = ["SecurityTokenResolver"]


@final
class SecurityTokenResolver:
    """Fills a route argument with the token the request authenticated.

    Where :class:`~xtr_security_http.resolver.user_value_resolver.UserValueResolver`
    hands an endpoint the *user*, this hands it the *token* — the roles
    authentication settled on, the attributes an authenticator attached — for
    an endpoint that decides something itself. An anonymous request against a
    marker that does not allow it raises
    :class:`~xtr_security_core.exception.AuthenticationCredentialsNotFoundError`,
    answered ``401``; an ``optional`` marker yields ``None`` instead.
    """

    __slots__ = ("_token_storage",)

    def __init__(self, token_storage: TokenStorageInterface) -> None:
        """Build the resolver over the request's token storage.

        Args:
            token_storage: Holds the token the firewall authenticated for
                this request.
        """
        self._token_storage = token_storage

    async def resolve(self, current_token: CurrentToken) -> TokenInterface | None:
        """Return the token ``current_token`` asks for, or ``None`` when it may.

        Raises:
            AuthenticationCredentialsNotFoundError: When no token is
                authenticated and ``current_token`` is not ``optional``.
        """
        token = self._token_storage.get_token()
        if token is None and not current_token.optional:
            raise AuthenticationCredentialsNotFoundError(
                "There is no authenticated token to pass to the argument; "
                "make the marker optional to allow anonymous access to the action.",
            )
        return token
