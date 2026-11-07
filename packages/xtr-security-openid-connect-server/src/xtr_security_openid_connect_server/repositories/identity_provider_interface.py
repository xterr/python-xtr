"""Where the user a token was issued for is found, with the claims they hold."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_security_oauth2_server_core.entities.client_entity_interface import (
        ClientEntityInterface,
    )

    from xtr_security_openid_connect_server.entities.user_claims_entity_interface import (
        UserClaimsEntityInterface,
    )

__all__ = ["IdentityProviderInterface"]


@runtime_checkable
class IdentityProviderInterface(Protocol):
    """Finds the user a token names, so the claims they granted can be read.

    A token carries its resource owner's identifier and nothing else: that is
    all the authorization server writes into one. Saying who that is — a name,
    an e-mail address, whatever the granted scopes reveal — takes the
    application's own users, and this is how they are reached. An application
    implements it over wherever it keeps them; the identity layer reads users
    through nothing else.

    The client is passed in as well, so a deployment can describe a user to
    one client more fully than to another.
    """

    async def get_user_entity_by_identifier(
        self,
        identifier: str,
        client: ClientEntityInterface,
    ) -> UserClaimsEntityInterface:
        """Return the user named ``identifier``, with the claims they hold.

        A user that cannot be found raises rather than answering ``None``: the
        identifier comes from a token this server issued, so a missing user is
        a failure to report, not an outcome to choose between. The error is the
        one the security family's user providers raise for a missing user
        (:class:`xtr_security_core.exception.UserNotFoundError`), so an
        implementation built on one of them lets it through as it is.

        Args:
            identifier: The resource owner's identifier, as the token names it.
            client: The client the token was issued to.

        Raises:
            UserNotFoundError: When no user matches ``identifier``.
        """
        ...
