"""What authentication settles on once an access token has been read."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_security_http.authenticator.token.post_authentication_token import (
    PostAuthenticationToken,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["OAuth2Token"]

#: The attribute the scope voter reads a token's scopes from, so that a route
#: asking for a scope is answered by the family's own authorization machinery
#: rather than by anything in this package.
SCOPE_ATTRIBUTE: Final = "oauth2_scope"

#: The attribute carrying the identifier of the access token the caller
#: presented, so a listener can tie a request back to the token it was made
#: with.
ACCESS_TOKEN_ID_ATTRIBUTE: Final = "access_token_id"  # noqa: S105 -- an attribute name, not a secret

#: The attribute carrying the client the access token was issued to.
CLIENT_ID_ATTRIBUTE: Final = "oauth_client_id"

#: The attribute carrying the scopes, under the name the reference server uses.
SCOPES_ATTRIBUTE: Final = "scopes"


@final
class OAuth2Token(PostAuthenticationToken):
    """The caller an access token proved, with its scopes read as roles.

    The scopes a token carries are turned into roles, each prefixed and upper
    cased, so that ``orders:read`` becomes ``ROLE_OAUTH2_ORDERS:READ``. That is
    what lets an access token be checked by exactly the same authorization
    rules as everything else: a route asking for a role does not have to know
    whether the caller arrived with a token or a session.

    The resource owner's own roles are kept beside them. A token is a grant
    *on top of* who somebody is, not instead of it — so a request is allowed
    what the token permits and what the person is, and a scope cannot be used
    to become somebody else.

    The scopes are also kept as they were, under their own attribute, because
    a role is lossy: it is upper cased and prefixed, and something asking "does
    this token carry ``orders:read``" wants the scope back exactly as issued.
    """

    _access_token_id: str
    _oauth_client_id: str
    _scopes: tuple[str, ...]

    def __init__(  # noqa: PLR0913, PLR0917 -- these five together are one authenticated caller
        self,
        user: UserInterface,
        firewall_name: str,
        access_token_id: str,
        oauth_client_id: str,
        scopes: Sequence[str],
        role_prefix: str,
    ) -> None:
        """Settle on ``user``, carrying ``scopes`` as roles under ``role_prefix``.

        Args:
            user: Who the token named — a resource owner, or the client itself
                when it authenticated for itself.
            firewall_name: The firewall that read the token.
            access_token_id: The identifier of the token presented.
            oauth_client_id: The client the token was issued to.
            scopes: The scopes the token carries, as issued.
            role_prefix: What each scope becomes a role under.
        """
        granted = tuple(f"{role_prefix}{scope}".strip().upper() for scope in scopes)
        # The user's own roles come after, and duplicates are dropped while the
        # order is kept, so a role granted by both appears once.
        roles = dict.fromkeys((*granted, *user.get_roles()))
        super().__init__(user, firewall_name, tuple(roles))
        self._access_token_id = access_token_id
        self._oauth_client_id = oauth_client_id
        self._scopes = tuple(scopes)
        self.set_attribute(ACCESS_TOKEN_ID_ATTRIBUTE, access_token_id)
        self.set_attribute(CLIENT_ID_ATTRIBUTE, oauth_client_id)
        self.set_attribute(SCOPES_ATTRIBUTE, self._scopes)
        self.set_attribute(SCOPE_ATTRIBUTE, self._scopes)

    def get_scopes(self) -> Sequence[str]:
        """Return the scopes the token carries, exactly as they were issued."""
        return self._scopes

    def get_credentials(self) -> str:
        """Return the identifier of the access token this caller presented."""
        return self._access_token_id

    def get_oauth_client_id(self) -> str:
        """Return the client the access token was issued to."""
        return self._oauth_client_id

    @override
    def __repr__(self) -> str:
        """Name the caller and the client, never the token's identifier.

        The identifier is what withdraws the token, so it stays out of a log
        line and a traceback; the scopes are left out for brevity, since the
        roles they became are readable wherever the token is.
        """
        return (
            f"{type(self).__name__}(user={self.get_user_identifier()!r}, "
            f"client={self.get_oauth_client_id()!r})"
        )
