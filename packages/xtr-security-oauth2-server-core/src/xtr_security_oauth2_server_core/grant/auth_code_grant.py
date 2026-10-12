"""A code handed to the browser is redeemed by the client for a token."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final

from typing_extensions import override

from xtr_security_oauth2_server_core.code_challenge_verifiers.plain_verifier import PlainVerifier
from xtr_security_oauth2_server_core.code_challenge_verifiers.s256_verifier import S256Verifier
from xtr_security_oauth2_server_core.exception.oauth2_error import OAuth2Error
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server_core.response_types.redirect_response import RedirectResponse

from .abstract_authorize_grant import AbstractAuthorizeGrant
from .abstract_grant import DEFAULT_REFRESH_TOKEN_TTL

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import timedelta

    from xtr_clock import ClockInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_oauth2_server_core.code_challenge_verifiers import (
        CodeChallengeVerifierInterface,
    )
    from xtr_security_oauth2_server_core.entities.auth_code_entity_interface import (
        AuthCodeEntityInterface,
    )
    from xtr_security_oauth2_server_core.entities.client_entity_interface import (
        ClientEntityInterface,
    )
    from xtr_security_oauth2_server_core.repositories.auth_code_repository_interface import (
        AuthCodeRepositoryInterface,
    )
    from xtr_security_oauth2_server_core.repositories.refresh_token_repository_interface import (
        RefreshTokenRepositoryInterface,
    )
    from xtr_security_oauth2_server_core.request_types.authorization_request_interface import (
        AuthorizationRequestInterface,
    )
    from xtr_security_oauth2_server_core.response_types.response_type_interface import (
        ResponseTypeInterface,
    )

__all__ = ["AuthCodeGrant"]

#: What a proof-key verifier, and the challenge made from it, may look like
#: (RFC 7636 sections 4.1 and 4.2). The floor of 43 characters is what makes
#: the verifier worth anything: a short one is guessable from the challenge.
_PROOF_KEY_PATTERN: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9\-._~]{43,128}")


class AuthCodeGrant(AbstractAuthorizeGrant):
    """Hands the browser a code, and the client exchanges it for a token.

    The flow every confidential client and every browser-based client should
    use. The token never travels through the browser: what the redirect carries
    is a short-lived code, and the client redeems it on a connection of its own
    where it can also prove who it is.

    The code is not stored state but sealed state: everything the token request
    has to know — which client it was issued to, for whom, for which scopes,
    against which proof key, until when — is encrypted into the code itself.
    Storage holds only whether the code has been redeemed, because a code is
    single use and that is the one fact the code cannot carry about itself.

    A public client cannot keep a secret, so it proves instead that the request
    redeeming the code came from whoever started the flow: it sends a digest up
    front and the secret behind it at the token endpoint. That is required of
    public clients unless a deployment turns the requirement off, and a code
    issued without a challenge may never be redeemed with a verifier — a client
    that could downgrade its own flow would hand that choice to whoever
    intercepted the redirect.
    """

    def __init__(
        self,
        dispatcher: EventDispatcherInterface,
        clock: ClockInterface,
        auth_code_repository: AuthCodeRepositoryInterface,
        refresh_token_repository: RefreshTokenRepositoryInterface,
        auth_code_ttl: timedelta,
    ) -> None:
        """Issue codes lasting ``auth_code_ttl`` through ``auth_code_repository``."""
        super().__init__(dispatcher, clock)
        self.set_auth_code_repository(auth_code_repository)
        self.set_refresh_token_repository(refresh_token_repository)
        self.set_refresh_token_ttl(DEFAULT_REFRESH_TOKEN_TTL)
        self._auth_code_ttl: timedelta = auth_code_ttl
        self._require_code_challenge_for_public_clients: bool = True
        verifiers: tuple[CodeChallengeVerifierInterface, ...] = (S256Verifier(), PlainVerifier())
        self._code_challenge_verifiers: dict[str, CodeChallengeVerifierInterface] = {
            verifier.get_method(): verifier for verifier in verifiers
        }

    def disable_require_code_challenge_for_public_clients(self) -> None:
        """Let a public client start this flow without a proof key.

        For a deployment with native clients too old to send one. Everything
        intercepting the redirect can then redeem the code.
        """
        self._require_code_challenge_for_public_clients = False

    @override
    def get_identifier(self) -> str:
        """Return ``authorization_code``, the name a request asks for this grant by."""
        return "authorization_code"

    @override
    def can_respond_to_authorization_request(self, request: ServerRequestInterface) -> bool:
        """Tell whether the request asks for a code from a named client."""
        query = request.get_query_params()

        return query.get("response_type") == "code" and "client_id" in query

    @override
    async def validate_authorization_request(
        self,
        request: ServerRequestInterface,
    ) -> AuthorizationRequestInterface:
        """Read ``request`` into the authorization request the consent step works on.

        Raises:
            OAuthServerError: When the request names no client or an unknown
                one, names a redirect URI the client did not register, asks for
                an unknown scope, carries a malformed proof key or one made by
                a method this server cannot judge, or comes from a public
                client with no proof key at all.
        """
        authorization_request = await self._read_authorization_request(request)
        code_challenge = self.get_query_string_parameter("code_challenge", request)
        if code_challenge is None:
            client = authorization_request.get_client()
            if self._require_code_challenge_for_public_clients and not client.is_confidential():
                raise OAuthServerError.invalid_request(
                    "code_challenge",
                    "Code challenge must be provided for public clients",
                )

            return authorization_request
        method = self.get_query_string_parameter("code_challenge_method", request) or "plain"
        if method not in self._code_challenge_verifiers:
            known = ", ".join(f"`{name}`" for name in self._code_challenge_verifiers)

            raise OAuthServerError.invalid_request(
                "code_challenge_method",
                f"Code challenge method must be one of {known}",
            )
        if _PROOF_KEY_PATTERN.fullmatch(code_challenge) is None:
            raise OAuthServerError.invalid_request(
                "code_challenge",
                "Code challenge must follow the specifications of RFC-7636.",
            )
        authorization_request.set_code_challenge(code_challenge)
        authorization_request.set_code_challenge_method(method)

        return authorization_request

    @override
    async def complete_authorization_request(
        self,
        request: ServerRequestInterface,
        authorization_request: AuthorizationRequestInterface,
    ) -> ResponseTypeInterface:
        """Send the browser back to the client with a code, or with the refusal.

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
                self.make_redirect_uri(answered_at, {"state": state}),
            )
        auth_code = await self.issue_auth_code(
            self._auth_code_ttl,
            authorization_request.get_client(),
            user.get_identifier(),
            authorization_request.get_redirect_uri(),
            authorization_request.get_scopes(),
        )
        sealed = self.encrypt(self.get_auth_code_payload(auth_code, authorization_request))
        response = RedirectResponse()
        response.set_redirect_uri(
            self.make_redirect_uri(answered_at, {"code": sealed, "state": state}),
        )

        return response

    def get_auth_code_payload(
        self,
        auth_code: AuthCodeEntityInterface,
        authorization_request: AuthorizationRequestInterface,
    ) -> dict[str, object]:
        """Return what the code carries, sealed, from the authorize step to the token one.

        This is the seam a deployment extends: something the token endpoint has
        to know about the original request — an identity nonce, the instant the
        resource owner authenticated — is added here by a subclass calling this
        and adding to what it answers, and read back out of the payload in its
        own token-endpoint code. Nothing else of the grant has to be copied.

        The expiry is read off the code rather than counted again, so a
        deployment overriding how codes are issued cannot end up with a code
        the payload outlives.
        """
        return {
            "client_id": auth_code.get_client().get_identifier(),
            "redirect_uri": auth_code.get_redirect_uri(),
            "auth_code_id": auth_code.get_identifier(),
            "scopes": [scope.get_identifier() for scope in auth_code.get_scopes()],
            "user_id": auth_code.get_user_identifier(),
            "expire_time": int(auth_code.get_expiry_date_time().timestamp()),
            "code_challenge": authorization_request.get_code_challenge(),
            "code_challenge_method": authorization_request.get_code_challenge_method(),
        }

    @override
    async def respond_to_access_token_request(
        self,
        request: ServerRequestInterface,
        response_type: ResponseTypeInterface,
        access_token_ttl: timedelta,
    ) -> ResponseTypeInterface:
        """Redeem the code in ``request`` for a token pair, and spend the code.

        Raises:
            OAuthServerError: When the client cannot be authenticated, the
                code is missing, unreadable, expired, already redeemed, issued
                to another client or for another redirect URI, or the proof
                key does not answer the challenge the code carries.
        """
        client = await self.validate_client(request)
        sealed = self.get_request_parameter("code", request)
        if sealed is None:
            raise OAuthServerError.invalid_request("code")
        try:
            payload = self.decrypt(sealed)
        except OAuth2Error as error:
            raise OAuthServerError.invalid_request(
                "code",
                "Issue decrypting the authorization code",
            ) from error
        auth_code_id = await self.validate_authorization_code(payload, client, request)
        granted = await self._scope_repository_or_fail().finalize_scopes(
            await self.validate_scopes(self._payload_names(payload, "scopes")),
            self.get_identifier(),
            client,
            self._payload_text(payload, "user_id"),
            auth_code_id,
        )
        self.validate_code_challenge(payload, self.get_request_parameter("code_verifier", request))
        await self._issue_tokens(
            request,
            response_type,
            access_token_ttl,
            client,
            self._payload_text(payload, "user_id"),
            granted,
        )
        await self._auth_code_repository_or_fail().revoke_auth_code(auth_code_id)

        return response_type

    async def validate_authorization_code(
        self,
        payload: Mapping[str, object],
        client: ClientEntityInterface,
        request: ServerRequestInterface,
    ) -> str:
        """Say that the code ``payload`` came from may be redeemed, and name it.

        It answers the identifier it validated rather than nothing, so the
        caller spends and finalises against the code this checked instead of
        reading the payload a second time.

        Raises:
            OAuthServerError: When the payload names no code, the code has
                expired or been redeemed, it was issued to another client, or
                the redirect URI does not match the one it was issued for.
        """
        auth_code_id = self._payload_text(payload, "auth_code_id")
        if auth_code_id is None:
            raise OAuthServerError.invalid_request("code", "Authorization code malformed")
        expire_time = self._payload_whole_number(payload, "expire_time")
        if expire_time is None or int(self._clock.now().timestamp()) > expire_time:
            raise OAuthServerError.invalid_grant("Authorization code has expired")
        if await self._auth_code_repository_or_fail().is_auth_code_revoked(auth_code_id):
            raise OAuthServerError.invalid_grant("Authorization code has been revoked")
        if self._payload_text(payload, "client_id") != client.get_identifier():
            raise OAuthServerError.invalid_request(
                "code",
                "Authorization code was not issued to this client",
            )
        issued_for = self._payload_text(payload, "redirect_uri")
        named = self.get_request_parameter("redirect_uri", request)
        if issued_for is not None and named is None:
            raise OAuthServerError.invalid_request("redirect_uri")
        if named is not None and issued_for != named:
            raise OAuthServerError.invalid_request("redirect_uri", "Invalid redirect URI")

        return auth_code_id

    def validate_code_challenge(
        self,
        payload: Mapping[str, object],
        code_verifier: str | None,
    ) -> None:
        """Judge ``code_verifier`` against the challenge the code carries.

        A code carrying no challenge is redeemed without one — and may not be
        redeemed *with* one: a verifier arriving for a code that never had a
        challenge is a client being talked into a flow weaker than the one it
        started, so it is refused rather than ignored.

        The challenge is judged by the method it was made with, read off the
        code, never by the method the token request names: letting the request
        choose would let a digest be redeemed as if it were the secret.

        Raises:
            OAuthServerError: When a verifier is missing, malformed, or does
                not answer the challenge; and when the code names a method
                this server cannot judge, which is this server's own fault.
        """
        challenge = self._payload_text(payload, "code_challenge")
        if challenge is None:
            if code_verifier is None:
                return

            raise OAuthServerError.invalid_request(
                "code_challenge",
                "code_verifier received when no code_challenge is present",
            )
        if code_verifier is None:
            raise OAuthServerError.invalid_request("code_verifier")
        if _PROOF_KEY_PATTERN.fullmatch(code_verifier) is None:
            raise OAuthServerError.invalid_request(
                "code_verifier",
                "Code Verifier must follow the specifications of RFC-7636.",
            )
        method = self._payload_text(payload, "code_challenge_method")
        verifier = None if method is None else self._code_challenge_verifiers.get(method)
        if verifier is None:
            raise OAuthServerError.server_error(f"Unsupported code challenge method `{method}`")
        if not verifier.verify_code_challenge(code_verifier, challenge):
            raise OAuthServerError.invalid_grant("Failed to verify `code_verifier`.")
