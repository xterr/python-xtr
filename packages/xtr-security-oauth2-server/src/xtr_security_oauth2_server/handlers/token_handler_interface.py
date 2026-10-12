"""What answers a request about a token the client already holds."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

    from xtr_security_oauth2_server.authorization_validators.bearer_token_validator_interface import (  # noqa: E501 -- one dotted path, nothing to break
        BearerTokenValidatorInterface,
    )
    from xtr_security_oauth2_server.repositories.access_token_repository_interface import (
        AccessTokenRepositoryInterface,
    )
    from xtr_security_oauth2_server.repositories.client_repository_interface import (
        ClientRepositoryInterface,
    )
    from xtr_security_oauth2_server.repositories.refresh_token_repository_interface import (
        RefreshTokenRepositoryInterface,
    )

__all__ = ["TokenHandlerInterface"]


@runtime_checkable
class TokenHandlerInterface(Protocol):
    """One endpoint that is about a token rather than about getting one.

    Withdrawing a token and asking whether one is live are the same request
    with two answers: the same body, the same client authentication, the same
    reading of the token. A handler is one of those answers, and the token
    server keeps one per endpoint, so a deployment replaces either without
    touching the other.

    The setters are not configuration a caller sprinkles about: the token
    server calls every one of them before a request reaches the handler, which
    is how a handler built with nothing but a dispatcher and a clock ends up
    holding the repositories, the reading of an access token and the key the
    whole server shares.
    """

    async def respond_to_request(
        self,
        request: ServerRequestInterface,
        response: ResponseInterface,
    ) -> ResponseInterface:
        """Answer ``request`` on top of ``response``.

        Raises:
            OAuthServerError: When the client cannot be authenticated, or the
                request names no token.
        """
        ...

    def set_client_repository(self, client_repository: ClientRepositoryInterface) -> None:
        """Take the repository registered clients are read from."""
        ...

    def set_access_token_repository(
        self,
        access_token_repository: AccessTokenRepositoryInterface,
    ) -> None:
        """Take the repository access tokens are withdrawn through."""
        ...

    def set_refresh_token_repository(
        self,
        refresh_token_repository: RefreshTokenRepositoryInterface,
    ) -> None:
        """Take the repository refresh tokens are read and withdrawn through."""
        ...

    def set_bearer_token_validator(
        self,
        bearer_token_validator: BearerTokenValidatorInterface,
    ) -> None:
        """Take what the access tokens this handler is handed are read by.

        It belongs to the contract rather than to a base class of ours because
        the token server hands it to whatever answers an endpoint: a handler a
        deployment installed reads an access token against the very store this
        server withdraws through, so a token the withdrawal endpoint has just
        taken away is one the question endpoint will not speak for either.
        """
        ...

    def set_encryption_key(self, key: str, key_type: Literal["plain", "key"]) -> None:
        """Take the key the refresh tokens this handler reads were sealed with."""
        ...
