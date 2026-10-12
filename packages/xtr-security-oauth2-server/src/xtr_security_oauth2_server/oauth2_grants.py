"""The grant types this server has a name for."""

from __future__ import annotations

from typing import Final, final

__all__ = ["OAuth2Grants"]


@final
class OAuth2Grants:
    """The grant-type identifiers, and the question of whether one is known.

    The names a request carries and a client's registration lists, in one
    place so a command validating what a person typed and a grant deciding
    whether it was asked for read the same strings.

    Two shapes appear here, and that is the protocol's doing: the original
    grants are plain words, while anything added later is a URN — a name
    nobody else can take.
    """

    AUTHORIZATION_CODE: Final[str] = "authorization_code"
    """A client redeems a code the resource owner's browser brought back."""

    CLIENT_CREDENTIALS: Final[str] = "client_credentials"
    """A client acts for itself, with no resource owner involved."""

    IMPLICIT: Final[str] = "implicit"
    """A token is handed straight to a browser. Off unless a deployment asks."""

    PASSWORD: Final[str] = "password"  # noqa: S105 -- a grant-type name, not a secret
    """A client sends a resource owner's own credentials. Off unless asked."""

    REFRESH_TOKEN: Final[str] = "refresh_token"  # noqa: S105 -- a grant-type name, not a secret
    """A client buys a new access token with a refresh token."""

    DEVICE_CODE: Final[str] = "urn:ietf:params:oauth:grant-type:device_code"
    """A device polls while its owner approves it on something with a keyboard."""

    @staticmethod
    def has(grant: str) -> bool:
        """Tell whether ``grant`` is one of the grant types named here.

        Says nothing about whether a deployment enabled it, or whether a
        client may use it — only that the name means something here. A command
        asks this before writing a registration nothing would ever match.
        """
        return grant in _KNOWN


#: Built once from the names above, so adding a grant type cannot leave the
#: question of whether it is known answering ``False``.
_KNOWN: Final[frozenset[str]] = frozenset(
    {
        OAuth2Grants.AUTHORIZATION_CODE,
        OAuth2Grants.CLIENT_CREDENTIALS,
        OAuth2Grants.IMPLICIT,
        OAuth2Grants.PASSWORD,
        OAuth2Grants.REFRESH_TOKEN,
        OAuth2Grants.DEVICE_CODE,
    },
)
