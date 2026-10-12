"""The server every endpoint goes through: grants in, protocol answers out."""

from __future__ import annotations

import copy
from datetime import timedelta
from typing import TYPE_CHECKING, Final, Literal, final

from typing_extensions import override

from xtr_security_oauth2_server_core._repeated_parameter import refuse_if_repeated
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server_core.oauth2_grants import OAuth2Grants
from xtr_security_oauth2_server_core.response_types.bearer_token_response import BearerTokenResponse

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

    from xtr_security_oauth2_server_core.entities.access_token_signer import AccessTokenSigner
    from xtr_security_oauth2_server_core.grant.grant_type_interface import GrantTypeInterface
    from xtr_security_oauth2_server_core.repositories.access_token_repository_interface import (
        AccessTokenRepositoryInterface,
    )
    from xtr_security_oauth2_server_core.repositories.client_repository_interface import (
        ClientRepositoryInterface,
    )
    from xtr_security_oauth2_server_core.repositories.scope_repository_interface import (
        ScopeRepositoryInterface,
    )
    from xtr_security_oauth2_server_core.request_types.authorization_request_interface import (
        AuthorizationRequestInterface,
    )
    from xtr_security_oauth2_server_core.response_types.response_type_interface import (
        ResponseTypeInterface,
    )

__all__ = ["DEFAULT_ACCESS_TOKEN_TTL", "AuthorizationServer"]

#: How long an access token lasts unless a grant was enabled with something
#: else. An hour is short enough that a token that escapes is of little use and
#: long enough that a client is not refreshing constantly.
DEFAULT_ACCESS_TOKEN_TTL: Final[timedelta] = timedelta(hours=1)


@final
class AuthorizationServer:
    """Runs the grants a deployment enabled, and answers every protocol endpoint.

    Nothing here knows a flow. A grant is enabled, the server hands it
    everything the whole server shares — the repositories, the signing key, the
    key its own payloads are sealed with, the default scope, whether a redeemed
    refresh token is withdrawn — and from then on every request is offered to
    each grant in turn until one says it can answer. Adding a flow to a
    deployment is registering another grant and nothing else.

    The response type is handed out per request as a shallow copy of the one
    this server owns. That is what keeps two requests being answered at the
    same time from reading each other's tokens: whatever a grant sets lands on
    a copy nobody else holds, while the services the copy shares with its
    original — a clock, anything a deployment injected into its own response
    type — are the same objects. The original is itself a copy of what the
    server was built with, so a response type registered once and handed to
    several servers is never written to by any of them.

    No answer is built here either: every endpoint is handed the response it is
    to answer on top of, and hands back what the flow made of it. Whoever is
    serving the request owns that response — which status and headers it starts
    out with, and what class it is — so this server runs in front of any
    framework without knowing one.
    """

    def __init__(  # noqa: PLR0913, PLR0917 -- these eight together are one server
        self,
        client_repository: ClientRepositoryInterface,
        access_token_repository: AccessTokenRepositoryInterface,
        scope_repository: ScopeRepositoryInterface,
        private_key: AccessTokenSigner,
        encryption_key: str,
        encryption_key_type: Literal["plain", "key"],
        dispatcher: EventDispatcherInterface,
        response_type: ResponseTypeInterface | None = None,
    ) -> None:
        """Build a server over the three stores every flow shares.

        Args:
            client_repository: Where registered clients are read from.
            access_token_repository: Where access tokens are minted, stored and
                withdrawn.
            scope_repository: Where scopes are read from and finalised.
            private_key: What the access tokens this server issues sign
                themselves with, and where it reads the time from.
            encryption_key: A password, or the base64url of a key's bytes.
            encryption_key_type: Which of the two ``encryption_key`` is.
            dispatcher: Where the grants and the endpoints announce what
                happened.
            response_type: What the token answer looks like, or ``None`` for the
                bearer document nearly every deployment hands out.
        """
        self._client_repository: ClientRepositoryInterface = client_repository
        self._access_token_repository: AccessTokenRepositoryInterface = access_token_repository
        self._scope_repository: ScopeRepositoryInterface = scope_repository
        self._private_key: AccessTokenSigner = private_key
        self._key_material: str = encryption_key
        self._key_type: Literal["plain", "key"] = encryption_key_type
        self._dispatcher: EventDispatcherInterface = dispatcher
        self._enabled_grant_types: dict[str, GrantTypeInterface] = {}
        self._grant_type_access_token_ttl: dict[str, timedelta] = {}
        self._default_scope: str = ""
        self._revoke_refresh_tokens: bool = True
        template = (
            BearerTokenResponse(private_key.clock)
            if response_type is None
            else copy.copy(response_type)
        )
        # The key is derived once per server rather than once per request: a
        # password costs real time to stretch on purpose, and the copy handed
        # to each request carries what the template already derived.
        template.set_encryption_key(encryption_key, encryption_key_type)
        self._response_type: ResponseTypeInterface = template

    def enable_grant_type(
        self,
        grant_type: GrantTypeInterface,
        access_token_ttl: timedelta | None = None,
    ) -> None:
        """Run ``grant_type`` on this server, issuing tokens for ``access_token_ttl``.

        Hands the grant everything the whole server shares, so a grant built
        with the two or three things only it needs arrives at its first request
        holding the repositories, the keys and the policies of the deployment
        it is part of.

        Enabling a grant twice replaces the first: a grant is known by the name
        requests ask for it by, and one name can mean one flow.
        """
        ttl = DEFAULT_ACCESS_TOKEN_TTL if access_token_ttl is None else access_token_ttl
        grant_type.set_access_token_repository(self._access_token_repository)
        grant_type.set_client_repository(self._client_repository)
        grant_type.set_scope_repository(self._scope_repository)
        grant_type.set_default_scope(self._default_scope)
        grant_type.set_private_key(self._private_key)
        grant_type.set_encryption_key(self._key_material, self._key_type)
        grant_type.revoke_refresh_tokens(self._revoke_refresh_tokens)
        self._enabled_grant_types[grant_type.get_identifier()] = grant_type
        self._grant_type_access_token_ttl[grant_type.get_identifier()] = ttl

    def set_default_scope(self, default_scope: str) -> None:
        """Read a request asking for no scope as asking for ``default_scope``.

        Set it before enabling the grants: a grant is handed the default scope
        when it is enabled, which is how it reaches the one place that turns a
        missing ``scope`` parameter into scopes.
        """
        self._default_scope = default_scope

    def revoke_refresh_tokens(self, revoke_refresh_tokens: bool) -> None:
        """Choose whether redeeming a refresh token withdraws it, for every grant.

        Set it before enabling the grants, for the same reason as
        :meth:`set_default_scope`.
        """
        self._revoke_refresh_tokens = revoke_refresh_tokens

    async def validate_authorization_request(
        self,
        request: ServerRequestInterface,
    ) -> AuthorizationRequestInterface:
        """Read ``request`` into the authorization request the consent step works on.

        The response type a request asks for is what decides which grant reads
        it, so a request naming none — or naming it twice — is refused before
        any grant is offered it. The grants read the name as it was sent, since
        all they do with it is claim the request; judging it is this server's,
        which is the only place that sees it before a flow has been chosen.

        Raises:
            OAuthServerError: ``invalid_request`` when the request names no
                response type or names it more than once, and
                ``unsupported_grant_type`` when no enabled grant answers
                requests like it.
        """
        query = request.get_query_params()
        if "response_type" not in query:
            raise OAuthServerError.invalid_request("response_type")
        refuse_if_repeated("response_type", query)
        for grant_type in self._enabled_grant_types.values():
            if grant_type.can_respond_to_authorization_request(request):
                return await grant_type.validate_authorization_request(request)

        raise OAuthServerError.unsupported_grant_type()

    async def complete_authorization_request(
        self,
        request: ServerRequestInterface,
        authorization_request: AuthorizationRequestInterface,
        response: ResponseInterface,
    ) -> ResponseInterface:
        """Finish an authorization request the resource owner has decided on.

        The grant that read the request is the one that finishes it, because
        only it knows what the flow hands back — a code, a token in a fragment.

        The request that carried the decision is passed in beside the
        authorization request, because a grant handing the token straight to
        the browser announces what it issued and an announcement names the
        request it happened during.

        Raises:
            InvalidArgumentError: When the grant the request was read by is no
                longer enabled, which means the server was reconfigured
                between the two halves of one flow.
            OAuthServerError: When the resource owner refused, in which case
                the refusal carries the redirect URI to deliver it to.
        """
        grant_type_id = authorization_request.get_grant_type_id()
        grant_type = self._enabled_grant_types.get(grant_type_id)
        if grant_type is None:
            raise InvalidArgumentError(
                f"The `{grant_type_id}` grant is not enabled on this server, so the "
                "authorization request it was read by cannot be completed; enable it with "
                "enable_grant_type().",
            )
        answered = await grant_type.complete_authorization_request(request, authorization_request)

        return answered.generate_http_response(response)

    async def respond_to_device_authorization_request(
        self,
        request: ServerRequestInterface,
        response: ResponseInterface,
    ) -> ResponseInterface:
        """Answer a device asking for the pair of codes it polls with.

        Raises:
            OAuthServerError: ``unsupported_grant_type`` when no enabled grant
                issues device codes.
        """
        for grant_type in self._enabled_grant_types.values():
            if grant_type.can_respond_to_device_authorization_request(request):
                answered = await grant_type.respond_to_device_authorization_request(request)

                return answered.generate_http_response(response)

        raise OAuthServerError.unsupported_grant_type()

    async def complete_device_authorization_request(
        self,
        device_code: str,
        user_id: str,
        user_approved: bool,
    ) -> None:
        """Record what the resource owner decided about ``device_code``.

        Raises:
            InvalidArgumentError: When the device flow is not enabled, so there
                is no device code to decide about.
            OAuthServerError: When no such device code is stored.
        """
        grant_type = self._enabled_grant_types.get(OAuth2Grants.DEVICE_CODE)
        if grant_type is None:
            raise InvalidArgumentError(
                f"The `{OAuth2Grants.DEVICE_CODE}` grant is not enabled on this server, so "
                "there is no device code to decide about; enable it with enable_grant_type().",
            )
        await grant_type.complete_device_authorization_request(
            device_code,
            user_id,
            user_approved,
        )

    async def respond_to_access_token_request(
        self,
        request: ServerRequestInterface,
        response: ResponseInterface,
    ) -> ResponseInterface:
        """Answer a token request with whatever the first grant that can says it earned.

        The grant type a request names is what decides which grant answers it,
        so a request naming it twice is refused before any grant is offered the
        request — for the same reason as in
        :meth:`validate_authorization_request`.

        Raises:
            OAuthServerError: ``invalid_request`` when the request names the
                grant type more than once, ``unsupported_grant_type`` when no
                enabled grant answers the grant type the request names, and
                whatever the grant refuses with otherwise.
        """
        refuse_if_repeated("grant_type", request.get_parsed_body())
        for grant_type in self._enabled_grant_types.values():
            if not grant_type.can_respond_to_access_token_request(request):
                continue
            answered = await grant_type.respond_to_access_token_request(
                request,
                copy.copy(self._response_type),
                self._grant_type_access_token_ttl[grant_type.get_identifier()],
            )

            return answered.generate_http_response(response)

        raise OAuthServerError.unsupported_grant_type()

    @override
    def __repr__(self) -> str:
        """Name what this server issues for and which flows it runs.

        Never the keys: this server holds the one its tokens are signed with
        and the one its payloads are sealed with, and neither belongs in a log
        line or a traceback.
        """
        return (
            f"{type(self).__name__}(issuer={self._private_key.issuer!r}, "
            f"grant_types={tuple(self._enabled_grant_types)!r})"
        )
