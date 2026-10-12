"""A client acting for itself exchanges its own credentials for a token."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server_core.request_event import RequestEvent

from .abstract_grant import AbstractGrant

if TYPE_CHECKING:
    from datetime import timedelta

    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_oauth2_server_core.response_types.response_type_interface import (
        ResponseTypeInterface,
    )

__all__ = ["ClientCredentialsGrant"]


@final
class ClientCredentialsGrant(AbstractGrant):
    """Issues a token to a client acting for nobody but itself.

    The simplest flow there is: a client proves who it is and is handed a token
    naming no resource owner. It is for a service talking to another service —
    a nightly job, a backend reading its own data — and never for a client
    acting on somebody's behalf, because there is nobody to ask.

    Only a confidential client may use it, and that is checked again after
    authentication: a public client has no secret to prove, so letting it in
    here would hand a token to whoever read the client identifier out of a
    published application.

    No refresh token is issued, because there is nothing to refresh: the client
    holds its own credentials and can ask for another token whenever it likes.
    """

    @override
    def get_identifier(self) -> str:
        """Return ``client_credentials``, the name a request asks for this grant by."""
        return "client_credentials"

    @override
    async def respond_to_access_token_request(
        self,
        request: ServerRequestInterface,
        response_type: ResponseTypeInterface,
        access_token_ttl: timedelta,
    ) -> ResponseTypeInterface:
        """Hand a confidential client a token for itself.

        Raises:
            OAuthServerError: When the client cannot be authenticated, is
                public, or asked for a scope this deployment does not know.
        """
        client = await self.validate_client(request)
        if not client.is_confidential():
            await self._announce(RequestEvent.CLIENT_AUTHENTICATION_FAILED, request)

            raise OAuthServerError.invalid_client(request)
        scopes = await self.validate_scopes(
            self.get_request_parameter("scope", request, self._default_scope_or_fail()),
        )
        granted = await self._scope_repository_or_fail().finalize_scopes(
            scopes,
            self.get_identifier(),
            client,
        )
        access_token = await self.issue_access_token(access_token_ttl, client, None, granted)
        await self._announce_access_token(request, access_token)
        response_type.set_access_token(access_token)

        return response_type
