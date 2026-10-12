"""A client that has seen the resource owner's own credentials exchanges them."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_oauth2_server.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server.request_event import RequestEvent

from .abstract_grant import DEFAULT_REFRESH_TOKEN_TTL, AbstractGrant

if TYPE_CHECKING:
    from datetime import timedelta

    from xtr_clock import ClockInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_oauth2_server.entities.client_entity_interface import ClientEntityInterface
    from xtr_security_oauth2_server.entities.user_entity_interface import UserEntityInterface
    from xtr_security_oauth2_server.repositories.refresh_token_repository_interface import (
        RefreshTokenRepositoryInterface,
    )
    from xtr_security_oauth2_server.repositories.user_repository_interface import (
        UserRepositoryInterface,
    )
    from xtr_security_oauth2_server.response_types.response_type_interface import (
        ResponseTypeInterface,
    )

__all__ = ["PasswordGrant"]


@final
class PasswordGrant(AbstractGrant):
    """Issues a token against a username and a password the client collected.

    The client asks the resource owner for their credentials itself and sends
    them here, which is exactly what the rest of the protocol exists to avoid:
    the client learns a password it has no business knowing, the resource owner
    never sees this server's own pages, and nothing of what they agreed to is
    recorded anywhere. It is here for deployments migrating something older,
    and it is off unless a deployment turns it on.

    The credentials are checked through the user repository, so what counts as
    a correct password stays the application's business. Every way of being
    wrong is answered the same way, because telling a caller which half it got
    wrong is how a list of accounts is built.
    """

    def __init__(
        self,
        dispatcher: EventDispatcherInterface,
        clock: ClockInterface,
        user_repository: UserRepositoryInterface,
        refresh_token_repository: RefreshTokenRepositoryInterface,
    ) -> None:
        """Check credentials against ``user_repository``, refresh through the other."""
        super().__init__(dispatcher, clock)
        self.set_user_repository(user_repository)
        self.set_refresh_token_repository(refresh_token_repository)
        self.set_refresh_token_ttl(DEFAULT_REFRESH_TOKEN_TTL)

    @override
    def get_identifier(self) -> str:
        """Return ``password``, the name a request asks for this grant by."""
        return "password"

    @override
    async def respond_to_access_token_request(
        self,
        request: ServerRequestInterface,
        response_type: ResponseTypeInterface,
        access_token_ttl: timedelta,
    ) -> ResponseTypeInterface:
        """Hand out a token for the resource owner whose credentials were sent.

        The scopes are read before the credentials are checked, so a request
        asking for a scope that does not exist is answered as the malformed
        request it is without a password being looked at.

        Raises:
            OAuthServerError: When the client cannot be authenticated, a scope
                is unknown, a credential is missing, or the credentials are
                wrong.
        """
        client = await self.validate_client(request)
        scopes = await self.validate_scopes(
            self.get_request_parameter("scope", request, self._default_scope_or_fail()),
        )
        user = await self.validate_user(request, client)
        granted = await self._scope_repository_or_fail().finalize_scopes(
            scopes,
            self.get_identifier(),
            client,
            user.get_identifier(),
        )
        await self._issue_tokens(
            request,
            response_type,
            access_token_ttl,
            client,
            user.get_identifier(),
            granted,
        )

        return response_type

    async def validate_user(
        self,
        request: ServerRequestInterface,
        client: ClientEntityInterface,
    ) -> UserEntityInterface:
        """Return the resource owner the credentials in ``request`` belong to.

        Raises:
            OAuthServerError: When a credential is missing, or the pair is not
                one this deployment recognises.
        """
        username = self.get_request_parameter("username", request)
        if username is None:
            raise OAuthServerError.invalid_request("username")
        password = self.get_request_parameter("password", request)
        if password is None:
            raise OAuthServerError.invalid_request("password")
        repository = self._user_repository_or_fail()
        user = await repository.get_user_entity_by_user_credentials(
            username,
            password,
            self.get_identifier(),
            client,
        )
        if user is None:
            await self._announce(RequestEvent.USER_AUTHENTICATION_FAILED, request)

            raise OAuthServerError.invalid_credentials()

        return user
