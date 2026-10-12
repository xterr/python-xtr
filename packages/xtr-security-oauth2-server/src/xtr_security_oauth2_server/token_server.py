"""The server the two endpoints about a token a client already holds go through."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, final

from typing_extensions import override

from xtr_security_oauth2_server.authorization_validators.bearer_token_validator import (
    BearerTokenValidator,
)
from xtr_security_oauth2_server.handlers.token_introspection_handler import (
    TokenIntrospectionHandler,
)
from xtr_security_oauth2_server.handlers.token_revocation_handler import TokenRevocationHandler

if TYPE_CHECKING:
    from datetime import timedelta

    from xtr_clock import ClockInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_jwt.services.jws_provider import JwsProviderInterface

    from xtr_security_oauth2_server.handlers.token_handler_interface import TokenHandlerInterface
    from xtr_security_oauth2_server.repositories.access_token_repository_interface import (
        AccessTokenRepositoryInterface,
    )
    from xtr_security_oauth2_server.repositories.client_repository_interface import (
        ClientRepositoryInterface,
    )
    from xtr_security_oauth2_server.repositories.refresh_token_repository_interface import (
        RefreshTokenRepositoryInterface,
    )

__all__ = ["TokenServer"]


@final
class TokenServer:
    """Answers the two requests that are about a token rather than about getting one.

    A client that is done with a token asks for it to be withdrawn (RFC 7009),
    and a resource server that cannot read a token asks whether it is live
    (RFC 7662). Neither is a flow, so neither belongs on the authorization
    server: they share a body, a client authentication and a reading of the
    token, and nothing else with the endpoints that issue tokens.

    This holds what both answers are made of and keeps one handler per
    endpoint, built the first time it is asked for and handed the repositories
    and the reading of a token again on every request — the handler shipped
    here and one a deployment installed alike, so a deployment that replaces
    either handler replaces that endpoint and nothing else.

    What reads an access token is built here rather than handed in, over the
    same access-token store this server withdraws through: a reading that
    judged revocation against another store would call a token live that this
    server had just withdrawn.

    The key refresh tokens were sealed with is handed to a handler when the
    handler is installed rather than on every request, because deriving a key
    from a password costs real time on purpose and a request must not pay it.

    Neither endpoint builds its answer: each is handed the response it is to
    answer on top of, so whoever is serving the request owns what the answer
    starts out as and what class it is.
    """

    def __init__(  # noqa: PLR0913, PLR0917 -- these eleven together are one server
        self,
        client_repository: ClientRepositoryInterface,
        access_token_repository: AccessTokenRepositoryInterface,
        refresh_token_repository: RefreshTokenRepositoryInterface,
        jws_provider: JwsProviderInterface,
        issuer: str,
        encryption_key: str,
        encryption_key_type: Literal["plain", "key"],
        dispatcher: EventDispatcherInterface,
        clock: ClockInterface,
        audience: str | None = None,
        leeway: timedelta | None = None,
    ) -> None:
        """Build a server over the three stores both endpoints read.

        Args:
            client_repository: Where registered clients are read from.
            access_token_repository: Where access tokens are withdrawn, and
                asked whether they already were.
            refresh_token_repository: Where refresh tokens are withdrawn, and
                asked whether they already were.
            jws_provider: Holds the keys an access token's signature is
                checked against.
            issuer: The origin an access token must claim to come from.
            encryption_key: A password, or the base64url of a key's bytes —
                the one the refresh tokens this server reads were sealed with.
            encryption_key_type: Which of the two ``encryption_key`` is.
            dispatcher: Where a failed client authentication is announced.
            clock: Where the instant a token is judged against is read from.
            audience: Who an access token must be addressed to, or ``None`` to
                accept whatever audience it names.
            leeway: How far the expiry and not-before windows are widened for
                clocks that disagree, or ``None`` for not at all.
        """
        self._client_repository: ClientRepositoryInterface = client_repository
        self._access_token_repository: AccessTokenRepositoryInterface = access_token_repository
        self._refresh_token_repository: RefreshTokenRepositoryInterface = refresh_token_repository
        self._jws_provider: JwsProviderInterface = jws_provider
        self._issuer: str = issuer
        self._key_material: str = encryption_key
        self._key_type: Literal["plain", "key"] = encryption_key_type
        self._dispatcher: EventDispatcherInterface = dispatcher
        self._clock: ClockInterface = clock
        self._audience: str | None = audience
        self._leeway: timedelta | None = leeway
        self._bearer_token_validator: BearerTokenValidator | None = None
        self._token_revocation_handler: TokenHandlerInterface | None = None
        self._token_introspection_handler: TokenHandlerInterface | None = None

    def set_token_revocation_handler(self, handler: TokenHandlerInterface) -> None:
        """Answer withdrawals with ``handler`` rather than with the shipped one."""
        handler.set_encryption_key(self._key_material, self._key_type)
        self._token_revocation_handler = handler

    def set_token_introspection_handler(self, handler: TokenHandlerInterface) -> None:
        """Answer questions about a token with ``handler`` rather than with the shipped one."""
        handler.set_encryption_key(self._key_material, self._key_type)
        self._token_introspection_handler = handler

    async def respond_to_token_revocation_request(
        self,
        request: ServerRequestInterface,
        response: ResponseInterface,
    ) -> ResponseInterface:
        """Withdraw the token ``request`` names, and answer that it is done.

        Raises:
            OAuthServerError: ``invalid_client`` when the client cannot be
                authenticated, ``invalid_request`` when the request names no
                token, and ``unsupported_token_type`` when the token was read
                as a kind this server does not withdraw.
        """
        return await self._revocation_handler().respond_to_request(request, response)

    async def respond_to_token_introspection_request(
        self,
        request: ServerRequestInterface,
        response: ResponseInterface,
    ) -> ResponseInterface:
        """Answer what this server will say about the token ``request`` names.

        Raises:
            OAuthServerError: ``invalid_client`` when the client cannot be
                authenticated, and ``invalid_request`` when the request names
                no token.
        """
        return await self._introspection_handler().respond_to_request(request, response)

    def _revocation_handler(self) -> TokenHandlerInterface:
        """Return the handler withdrawals are answered by, built the first time."""
        handler = self._token_revocation_handler
        if handler is None:
            handler = TokenRevocationHandler(self._dispatcher, self._clock)
            self.set_token_revocation_handler(handler)

        return self._wire(handler)

    def _introspection_handler(self) -> TokenHandlerInterface:
        """Return the handler questions about a token are answered by, built the first time."""
        handler = self._token_introspection_handler
        if handler is None:
            handler = TokenIntrospectionHandler(self._dispatcher, self._clock)
            self.set_token_introspection_handler(handler)

        return self._wire(handler)

    def _wire(self, handler: TokenHandlerInterface) -> TokenHandlerInterface:
        """Hand ``handler`` the stores and the reading both endpoints share, and answer it."""
        handler.set_client_repository(self._client_repository)
        handler.set_access_token_repository(self._access_token_repository)
        handler.set_refresh_token_repository(self._refresh_token_repository)
        handler.set_bearer_token_validator(self._validator())

        return handler

    def _validator(self) -> BearerTokenValidator:
        """Return what the access tokens handed to either endpoint are read by."""
        if self._bearer_token_validator is None:
            self._bearer_token_validator = BearerTokenValidator(
                self._access_token_repository,
                self._jws_provider,
                self._issuer,
                self._clock,
                self._audience,
                self._leeway,
            )

        return self._bearer_token_validator

    @override
    def __repr__(self) -> str:
        """Name what this server answers for, and nothing it holds.

        Never the keys: this server holds the one its payloads were sealed
        with and the provider holding the verifying keys, and neither belongs
        in a log line or a traceback.
        """
        return f"{type(self).__name__}(issuer={self._issuer!r}, audience={self._audience!r})"
