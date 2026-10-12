"""What a resource server reads an incoming request through."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["AuthorizationValidatorInterface"]


@runtime_checkable
class AuthorizationValidatorInterface(Protocol):
    """Works out which token a request carries, and whether it still stands.

    One method, and it answers a request rather than a token: whatever was
    read — the token's identifier, the client, the resource owner, the scopes —
    is written onto the request as attributes, so every step after this one
    reads a request that already knows who is calling and needs no second
    argument threaded through it.

    It is awaitable because judging a token may mean asking storage whether it
    was revoked, which is the one thing a self-describing token cannot say
    about itself.
    """

    async def validate_authorization(
        self,
        request: ServerRequestInterface,
    ) -> ServerRequestInterface:
        """Return ``request`` annotated with what the token it carries says.

        Raises:
            OAuthServerError: ``access_denied`` when the request carries no
                token, or one that cannot be accepted.
        """
        ...
