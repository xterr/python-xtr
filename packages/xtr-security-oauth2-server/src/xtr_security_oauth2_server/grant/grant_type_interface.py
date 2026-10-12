"""What every grant answers to, so the server runs one without knowing which."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import timedelta

    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_oauth2_server.entities.access_token_signer import AccessTokenSigner
    from xtr_security_oauth2_server.repositories.access_token_repository_interface import (
        AccessTokenRepositoryInterface,
    )
    from xtr_security_oauth2_server.repositories.client_repository_interface import (
        ClientRepositoryInterface,
    )
    from xtr_security_oauth2_server.repositories.scope_repository_interface import (
        ScopeRepositoryInterface,
    )
    from xtr_security_oauth2_server.request_types.authorization_request_interface import (
        AuthorizationRequestInterface,
    )
    from xtr_security_oauth2_server.response_types.device_code_response import DeviceCodeResponse
    from xtr_security_oauth2_server.response_types.response_type_interface import (
        ResponseTypeInterface,
    )

__all__ = ["GrantTypeInterface"]


@runtime_checkable
class GrantTypeInterface(Protocol):
    """One way of turning something a client holds into a token.

    A grant is the whole of a flow: it says which requests it can answer, reads
    them, decides what they have earned and issues it. The authorization server
    keeps a grant per identifier and asks each in turn which can answer the
    request in front of it, so adding a flow to a deployment is registering
    another one of these and nothing else.

    The setters are not configuration a caller sprinkles about: the server
    calls every one of them when a grant is enabled, which is how a grant built
    with the two or three things only it needs ends up holding the repositories,
    the keys and the default scope that the whole server shares. A grant used
    before that has happened refuses to work rather than inventing a stand-in.

    Three of the methods belong to the device flow alone and the rest of the
    grants refuse them. They are on the contract rather than on a second one
    because the server asks every grant whether it can answer a device
    authorization request, and a contract per flow would turn that question
    into a type check.
    """

    def get_identifier(self) -> str:
        """Return the name a request asks for this grant by."""
        ...

    def set_client_repository(self, client_repository: ClientRepositoryInterface) -> None:
        """Take the repository registered clients are read from."""
        ...

    def set_access_token_repository(
        self,
        access_token_repository: AccessTokenRepositoryInterface,
    ) -> None:
        """Take the repository access tokens are minted and stored through."""
        ...

    def set_scope_repository(self, scope_repository: ScopeRepositoryInterface) -> None:
        """Take the repository scopes are read from and finalised through."""
        ...

    def set_default_scope(self, scope: str) -> None:
        """Take the scopes a request asking for none is read as asking for."""
        ...

    def set_private_key(self, private_key: AccessTokenSigner) -> None:
        """Take what the access tokens this grant issues sign themselves with."""
        ...

    def set_encryption_key(self, key: str, key_type: Literal["plain", "key"]) -> None:
        """Take the key this grant seals the state it hands to clients with."""
        ...

    def set_refresh_token_ttl(self, refresh_token_ttl: timedelta) -> None:
        """Take how long the refresh tokens this grant issues last."""
        ...

    def revoke_refresh_tokens(self, will_revoke: bool) -> None:
        """Choose whether redeeming a refresh token revokes it."""
        ...

    async def respond_to_access_token_request(
        self,
        request: ServerRequestInterface,
        response_type: ResponseTypeInterface,
        access_token_ttl: timedelta,
    ) -> ResponseTypeInterface:
        """Answer a token request, setting what it earned on ``response_type``.

        The response type is handed in rather than built here, so one grant
        serves whatever document a deployment hands out.

        Raises:
            OAuthServerError: When the request cannot be honoured.
        """
        ...

    def can_respond_to_access_token_request(self, request: ServerRequestInterface) -> bool:
        """Tell whether this grant is the one ``request`` is asking for."""
        ...

    def can_respond_to_authorization_request(self, request: ServerRequestInterface) -> bool:
        """Tell whether this grant answers authorization requests like ``request``."""
        ...

    async def validate_authorization_request(
        self,
        request: ServerRequestInterface,
    ) -> AuthorizationRequestInterface:
        """Read ``request`` into the authorization request the consent step works on.

        Raises:
            OAuthServerError: When the request cannot be honoured.
        """
        ...

    async def complete_authorization_request(
        self,
        request: ServerRequestInterface,
        authorization_request: AuthorizationRequestInterface,
    ) -> ResponseTypeInterface:
        """Finish an authorization request the resource owner has decided on.

        The request is passed in beside it because the grant announces what it
        issued, and an announcement names the request it happened during — the
        one carrying the decision, not the one that started the flow.

        Raises:
            OAuthServerError: When the resource owner refused, in which case
                the refusal carries the redirect URI to deliver it to.
        """
        ...

    def can_respond_to_device_authorization_request(self, request: ServerRequestInterface) -> bool:
        """Tell whether this grant answers device authorization requests."""
        ...

    async def respond_to_device_authorization_request(
        self,
        request: ServerRequestInterface,
    ) -> DeviceCodeResponse:
        """Issue the pair of codes a device polls and its owner types in.

        Raises:
            OAuthServerError: When the request cannot be honoured.
        """
        ...

    async def complete_device_authorization_request(
        self,
        device_code: str,
        user_id: str,
        user_approved: bool,
    ) -> None:
        """Record what the resource owner decided about a device code.

        Raises:
            OAuthServerError: When no such device code is stored, or no
                resource owner was named.
        """
        ...

    def set_interval_visibility(self, interval_visibility: bool) -> None:
        """Choose whether a device is told how long to wait between polls."""
        ...

    def get_interval_visibility(self) -> bool:
        """Tell whether a device is told how long to wait between polls."""
        ...

    def set_include_verification_uri_complete(
        self,
        include_verification_uri_complete: bool,
    ) -> None:
        """Choose whether a device is sent the verification URI with its code in it."""
        ...
