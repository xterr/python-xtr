"""The browser is handed the token itself, in the fragment."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server_core.response_types.redirect_response import RedirectResponse

from .abstract_authorize_grant import AbstractAuthorizeGrant

if TYPE_CHECKING:
    from datetime import timedelta

    from xtr_clock import ClockInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_oauth2_server_core.repositories.refresh_token_repository_interface import (
        RefreshTokenRepositoryInterface,
    )
    from xtr_security_oauth2_server_core.request_types.authorization_request_interface import (
        AuthorizationRequestInterface,
    )
    from xtr_security_oauth2_server_core.response_types.response_type_interface import (
        ResponseTypeInterface,
    )

__all__ = ["ImplicitGrant"]

_NO_REFRESH_TOKENS = (
    "The implicit grant issues no refresh tokens, so it has nothing to do with a refresh "
    "token repository or lifetime; a client that needs one uses the authorization code grant."
)

_WRONG_ENDPOINT = (
    "The implicit grant is never used at the token endpoint: it hands the token straight to "
    "the browser when the authorization request is completed."
)


@final
class ImplicitGrant(AbstractAuthorizeGrant):
    """Hands the access token to the browser, in the redirect's fragment.

    The flow the rest of the protocol has moved away from. There is no second
    request in which a client could prove anything, so the token is handed to
    whatever followed the redirect: it ends up in browser history, in a
    referrer, in whatever reads the address bar. It is here for deployments
    with something older still pointing at it, and it is off unless a
    deployment turns it on.

    It puts its answer in the fragment rather than in the query, which is the
    one protection the flow has: a fragment is not sent to a server, so the
    token does not land in an access log on the way.

    No refresh token is issued, and the two ways of asking for one refuse
    rather than being quietly ignored — a deployment that configured a refresh
    lifetime here has misunderstood the flow, and should be told so at the
    point it says it.
    """

    def __init__(
        self,
        dispatcher: EventDispatcherInterface,
        clock: ClockInterface,
        access_token_ttl: timedelta,
        query_delimiter: str = "#",
    ) -> None:
        """Hand out tokens lasting ``access_token_ttl``, in the fragment by default."""
        super().__init__(dispatcher, clock)
        self._access_token_ttl: timedelta = access_token_ttl
        self._query_delimiter: str = query_delimiter

    @override
    def get_identifier(self) -> str:
        """Return ``implicit``, the name this grant is known by."""
        return "implicit"

    @override
    def set_refresh_token_ttl(self, refresh_token_ttl: timedelta) -> None:
        """Refuse a refresh-token lifetime this grant would never use.

        Raises:
            InvalidArgumentError: Always.
        """
        del refresh_token_ttl

        raise InvalidArgumentError(_NO_REFRESH_TOKENS)

    @override
    def set_refresh_token_repository(
        self,
        refresh_token_repository: RefreshTokenRepositoryInterface,
    ) -> None:
        """Refuse a refresh-token repository this grant would never reach.

        Raises:
            InvalidArgumentError: Always.
        """
        del refresh_token_repository

        raise InvalidArgumentError(_NO_REFRESH_TOKENS)

    @override
    def can_respond_to_access_token_request(self, request: ServerRequestInterface) -> bool:
        """Answer no: this flow is finished before the token endpoint is reached."""
        del request

        return False

    @override
    async def respond_to_access_token_request(
        self,
        request: ServerRequestInterface,
        response_type: ResponseTypeInterface,
        access_token_ttl: timedelta,
    ) -> ResponseTypeInterface:
        """Say that this grant is not used at the token endpoint.

        Raises:
            InvalidArgumentError: Always.
        """
        del request, response_type, access_token_ttl

        raise InvalidArgumentError(_WRONG_ENDPOINT)

    @override
    def can_respond_to_authorization_request(self, request: ServerRequestInterface) -> bool:
        """Tell whether the request asks for a token from a named client."""
        query = request.get_query_params()

        return query.get("response_type") == "token" and "client_id" in query

    @override
    async def validate_authorization_request(
        self,
        request: ServerRequestInterface,
    ) -> AuthorizationRequestInterface:
        """Read ``request`` into the authorization request the consent step works on.

        Raises:
            OAuthServerError: When the request names no client or an unknown
                one, names a redirect URI the client did not register, or asks
                for an unknown scope.
        """
        return await self._read_authorization_request(request, self._query_delimiter)

    @override
    async def complete_authorization_request(
        self,
        request: ServerRequestInterface,
        authorization_request: AuthorizationRequestInterface,
    ) -> ResponseTypeInterface:
        """Send the browser back to the client with the token, or with the refusal.

        The token is announced like any other, naming the request that carried
        the decision — which is why that request is passed in rather than the
        one that started the flow.

        Raises:
            InvalidArgumentError: When nothing resolved who the resource owner
                is.
            OAuthServerError: When the resource owner refused, carrying the
                redirect URI the refusal is to be delivered to.
        """
        user = self._resource_owner_or_fail(authorization_request)
        answered_at = self._answered_at(authorization_request)
        state = authorization_request.get_state()
        if not authorization_request.is_authorization_approved():
            raise OAuthServerError.access_denied(
                "The user denied the request",
                self.make_redirect_uri(answered_at, {"state": state}, self._query_delimiter),
            )
        client = authorization_request.get_client()
        granted = await self._scope_repository_or_fail().finalize_scopes(
            authorization_request.get_scopes(),
            self.get_identifier(),
            client,
            user.get_identifier(),
        )
        access_token = await self.issue_access_token(
            self._access_token_ttl,
            client,
            user.get_identifier(),
            granted,
        )
        await self._announce_access_token(request, access_token)
        expiry = access_token.get_expiry_date_time().timestamp()
        response = RedirectResponse()
        response.set_redirect_uri(
            self.make_redirect_uri(
                answered_at,
                {
                    "access_token": access_token.to_string(),
                    "token_type": "Bearer",
                    "expires_in": int(expiry - self._clock.now().timestamp()),
                    "state": state,
                },
                self._query_delimiter,
            ),
        )

        return response
