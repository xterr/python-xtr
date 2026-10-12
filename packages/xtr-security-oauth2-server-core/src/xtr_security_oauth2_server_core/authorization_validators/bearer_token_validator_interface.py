"""What reads a bearer token and says what it claims, for whoever holds one."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["BearerTokenValidatorInterface"]


@runtime_checkable
class BearerTokenValidatorInterface(Protocol):
    """Judges one access token and hands back what it says.

    This is the half of reading a request that is about the token alone, with
    no ``Authorization`` header around it: a resource server reaches it
    through :class:`AuthorizationValidatorInterface`, while the handlers that
    answer about a token the client already holds have the token in the
    request body and need nothing else.

    It answers the claims rather than a request, because the caller decides
    what to do with them — write them onto a request, repeat them back in a
    document about the token, or read one of them to know which token to
    revoke.

    It is awaitable because judging a token may mean asking storage whether it
    was revoked, which is the one thing a self-describing token cannot say
    about itself.
    """

    async def validate_bearer_token(
        self,
        request: ServerRequestInterface,
        token: str,
    ) -> Mapping[str, object]:
        """Return what ``token`` claims, having refused every reason not to.

        Raises:
            OAuthServerError: ``access_denied`` when the token cannot be
                accepted.
        """
        ...
