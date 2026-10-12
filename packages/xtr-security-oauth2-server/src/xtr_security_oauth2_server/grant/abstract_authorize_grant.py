"""What the two grants that end in a redirect share."""

from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING

from xtr_security_oauth2_server._redirect_uri import NO_PARAMS, redirect_uri_carrying
from xtr_security_oauth2_server.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server.request_event import RequestEvent
from xtr_security_oauth2_server.request_types.authorization_request import AuthorizationRequest

from .abstract_grant import AbstractGrant

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_oauth2_server.entities.client_entity_interface import ClientEntityInterface
    from xtr_security_oauth2_server.entities.user_entity_interface import UserEntityInterface
    from xtr_security_oauth2_server.request_types.authorization_request_interface import (
        AuthorizationRequestInterface,
    )

__all__ = ["AbstractAuthorizeGrant"]

_NO_RESOURCE_OWNER = (
    "This authorization request names no resource owner, so there is nobody to issue for; "
    "whatever resolves consent sets one with set_user() before the request is completed."
)


class AbstractAuthorizeGrant(AbstractGrant, ABC):
    """Builds the redirect an authorization request ends in.

    A flow that asks the resource owner anything ends the same way: the browser
    is sent back to the client with the result in the URI. What the result is —
    an authorization code to redeem, or the access token itself — is the only
    difference, and so is whether it travels in the query or in the fragment.

    The three methods here are the seams the grants above them reach through,
    and each exists because a deployment may need to change it: an add-on
    carrying something of its own across the consent step replaces the
    authorization request, and one with its own view of which registered URI to
    answer at replaces the last.
    """

    def make_redirect_uri(
        self,
        uri: str,
        params: Mapping[str, str | int | None] = NO_PARAMS,
        query_delimiter: str = "?",
    ) -> str:
        """Return ``uri`` carrying ``params``, in its query or in its fragment.

        A parameter whose value is absent is left out rather than sent empty,
        because a client reads ``state=`` as state it never sent.

        A seam a subclass may replace; what it does is the package's one way
        of building such a URI, which the authorization endpoint uses too.

        Args:
            uri: Where the browser is being sent.
            params: What to carry there.
            query_delimiter: ``?`` to carry them in the query, ``#`` to carry
                them in the fragment — which is what an access token handed
                straight to a browser uses, so it never reaches a server log.
        """
        return redirect_uri_carrying(uri, params, query_delimiter)

    def create_authorization_request(self) -> AuthorizationRequestInterface:
        """Return the request this grant records what it read into.

        A deployment that has to carry something extra across the consent step
        — a nonce, the instant the resource owner authenticated — overrides
        this with a request of its own and the grant goes on filling it in.
        """
        return AuthorizationRequest()

    def get_client_redirect_uri(self, client: ClientEntityInterface) -> str:
        """Return where ``client`` is answered when the request named nowhere.

        A client registered with several URIs and asking for none is answered
        at the first, which is only ever reached once the grant has established
        that exactly one is registered.
        """
        registered = client.get_redirect_uri()

        return registered if isinstance(registered, str) else registered[0]

    def _has_one_registered_redirect_uri(self, client: ClientEntityInterface) -> bool:
        """Tell whether ``client`` registered exactly one URI to be answered at.

        A request naming no redirect URI is only answerable then: a client with
        several registered has not said which, and one with none registered has
        nowhere to be answered at all.
        """
        registered = client.get_redirect_uri()
        if isinstance(registered, str):
            return registered != ""

        return len(registered) == 1

    async def _read_authorization_request(
        self,
        request: ServerRequestInterface,
        query_delimiter: str = "?",
    ) -> AuthorizationRequestInterface:
        """Read what both authorize flows read the same way out of ``request``.

        Which client is asking, where it may be answered, the state to hand
        back and the scopes it wants. What is left over is what makes the two
        flows different: the proof key one of them requires, and nothing in the
        other.

        A refusal about the scopes is delivered to the client, carrying the
        state, so a browser that asked for something unknown ends up back where
        it started rather than looking at this server's error page.

        Args:
            request: The authorization request as it arrived.
            query_delimiter: ``?`` when the answer travels in the query, ``#``
                when it travels in the fragment.

        Raises:
            OAuthServerError: When no client is named, it is not registered,
                the redirect URI is not one of its own or it named none while
                several are registered, or a scope is unknown.
        """
        basic_user, _ = self.get_basic_auth_credentials(request)
        client_id = self.get_query_string_parameter("client_id", request, basic_user)
        if client_id is None:
            raise OAuthServerError.invalid_request("client_id")
        client = await self.get_client_entity_or_fail(client_id, request)
        redirect_uri = self.get_query_string_parameter("redirect_uri", request)
        if redirect_uri is not None:
            await self.validate_redirect_uri(redirect_uri, client, request)
        elif not self._has_one_registered_redirect_uri(client):
            await self._announce(RequestEvent.CLIENT_AUTHENTICATION_FAILED, request)

            raise OAuthServerError.invalid_client(request)
        state = self.get_query_string_parameter("state", request)
        answered_at = (
            redirect_uri if redirect_uri is not None else self.get_client_redirect_uri(client)
        )
        scopes = await self.validate_scopes(
            self.get_query_string_parameter("scope", request, self._default_scope_or_fail()),
            self.make_redirect_uri(answered_at, {"state": state}, query_delimiter),
        )
        authorization_request = self.create_authorization_request()
        authorization_request.set_grant_type_id(self.get_identifier())
        authorization_request.set_client(client)
        authorization_request.set_redirect_uri(redirect_uri)
        if state is not None:
            authorization_request.set_state(state)
        authorization_request.set_scopes(scopes)

        return authorization_request

    def _answered_at(self, authorization_request: AuthorizationRequestInterface) -> str:
        """Return where the browser is sent once the resource owner has decided."""
        named = authorization_request.get_redirect_uri()
        if named is not None:
            return named

        return self.get_client_redirect_uri(authorization_request.get_client())

    def _resource_owner_or_fail(
        self,
        authorization_request: AuthorizationRequestInterface,
    ) -> UserEntityInterface:
        """Return the resource owner the request was decided by.

        Raises:
            InvalidArgumentError: When nothing set one, which means the consent
                step was skipped and there is nobody to issue a token for.
        """
        user = authorization_request.get_user()
        if user is None:
            raise InvalidArgumentError(_NO_RESOURCE_OWNER)

        return user
