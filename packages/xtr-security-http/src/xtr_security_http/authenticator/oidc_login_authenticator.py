"""The authenticator for the OpenID Connect Authorization Code Flow."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_clock import SystemClock
from xtr_security_core.exception import AuthenticationError

from xtr_security_http._parked_session import parked_session_of
from xtr_security_http.entry_point.authentication_entry_point_interface import (
    AuthenticationEntryPointInterface,
)
from xtr_security_http.entry_point.re_authentication_entry_point_interface import (
    ReAuthenticationEntryPointInterface,
)
from xtr_security_http.exception import MissingSessionError
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from ._oidc_login_attempts import OidcLoginAttempts
from ._oidc_login_authorization import OidcLoginAuthorization
from ._oidc_login_callback import check_issuer, check_provider_error, read_callback
from ._oidc_login_claims import build_passport, fetch_user_claims
from ._oidc_login_options import OidcLoginOptions, managed_params_of
from ._oidc_login_public_client import check_public_client
from ._oidc_login_token import stamp_oidc_token
from .abstract_authenticator import AbstractAuthenticator
from .debug.unsupported_reasons import UnsupportedReasons
from .interactive_authenticator_interface import InteractiveAuthenticatorInterface
from .token.post_authentication_token import PostAuthenticationToken

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_clock import ClockInterface
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_foundation import Session
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_provider_interface import UserProviderInterface

    from xtr_security_http.authentication.authentication_failure_handler_interface import (
        AuthenticationFailureHandlerInterface,
    )
    from xtr_security_http.authentication.authentication_success_handler_interface import (
        AuthenticationSuccessHandlerInterface,
    )
    from xtr_security_http.http_utils import HttpUtils
    from xtr_security_http.oidc.oidc_client_interface import OidcClientInterface
    from xtr_security_http.oidc.oidc_discovery import OidcDiscovery
    from xtr_security_http.oidc.oidc_id_token import OidcIdToken
    from xtr_security_http.oidc.oidc_signature_verifier import OidcSignatureVerifier

    from .passport.passport import Passport

__all__ = ["OidcLoginAuthenticator"]


@final
class OidcLoginAuthenticator(
    AbstractAuthenticator,
    AuthenticationEntryPointInterface,
    InteractiveAuthenticatorInterface,
    ReAuthenticationEntryPointInterface,
):
    """Authenticates a user through the OpenID Connect Authorization Code Flow.

    See https://openid.net/specs/openid-connect-core-1_0.html#CodeFlowAuth.

    The entry point sends an authorization request — a PKCE challenge, a
    state and a nonce of its own, all three stored in the session under keys
    of their own, capped — and the callback exchanges the code for tokens,
    verifies the ID token's signature before its claims are read, validates
    the claims against the issuer, the client, the nonce and the requested
    ``max_age``, and loads the user from the claims the configured source
    names. The tokens travel to the security token as ``oidc_*`` attributes,
    where the refresher renews them and the back-channel logout finds its
    ``sid``.
    """

    __slots__ = (
        "_authorization",
        "_client_id",
        "_clock",
        "_failure_handler",
        "_id_token",
        "_oidc_client",
        "_options",
        "_signature_verifier",
        "_success_handler",
        "_user_provider",
    )

    def __init__(  # noqa: PLR0913, PLR0917 -- the upstream wiring shape: the collaborators the flow needs, each with its own role
        self,
        http_utils: HttpUtils,
        user_provider: UserProviderInterface,
        oidc_client: OidcClientInterface,
        discovery: OidcDiscovery,
        id_token: OidcIdToken,
        client_id: str,
        success_handler: AuthenticationSuccessHandlerInterface,
        failure_handler: AuthenticationFailureHandlerInterface,
        options: Mapping[str, object] | None = None,
        authorization_params: Mapping[str, str] | None = None,
        signature_verifier: OidcSignatureVerifier | None = None,
        clock: ClockInterface | None = None,
        event_dispatcher: EventDispatcherInterface | None = None,
    ) -> None:
        """Record the collaborators of the flow and the shape the wiring gives it.

        Args:
            http_utils: Matches the check path and builds the redirects.
            user_provider: Loads the user the identifier claim names.
            oidc_client: Runs the protocol operations against the provider.
            discovery: Reads the endpoints and the issuer off the provider's
                discovery document.
            id_token: Decodes and validates the ID token's claims.
            client_id: The client's identifier, its registration at the
                provider.
            success_handler: Answers a successful login.
            failure_handler: Answers a failed one.
            options: The flow's shape, merged over the defaults.
            authorization_params: Additional parameters of the authorization
                request, e.g. ``prompt`` or ``ui_locales``; the protocol
                parameters the authenticator manages itself are rejected.
                Listen to the authorization-request event to compute them per
                request.
            signature_verifier: Verifies the ID token's signature against the
                provider's JWKS, or ``None`` to decode the token without
                verifying it, which OIDC Core 1.0, Section 3.1.3.7, item 6
                only allows as long as the token endpoint request verifies
                TLS.
            clock: What the access token's absolute expiry is read on, or
                ``None`` to use the system time.
            event_dispatcher: Dispatches the authorization-request event
                before the user is redirected to the provider, or ``None`` to
                always send the authorization request ``authorization_params``
                describes.

        Raises:
            InvalidArgumentError: When ``options`` names a PKCE method RFC
                7636 does not define, or when ``authorization_params``
                carries a parameter the authenticator manages itself.
        """
        self._http_utils = http_utils
        self._user_provider = user_provider
        self._discovery = discovery
        self._oidc_client = oidc_client
        self._id_token = id_token
        self._client_id = client_id
        self._success_handler = success_handler
        self._failure_handler = failure_handler
        self._options = OidcLoginOptions.merge(options)
        authorization_params = dict(authorization_params or {})
        _ = managed_params_of(authorization_params)
        self._signature_verifier = signature_verifier
        self._clock = clock if clock is not None else SystemClock()
        self._authorization = OidcLoginAuthorization(
            http_utils,
            discovery,
            event_dispatcher,
            self._options,
            client_id,
            authorization_params,
        )

    @override
    def supports(self, request: ServerRequestInterface) -> bool:
        """Handle every request on the callback path.

        The route declared for it carries no controller, so one passing
        through would end up reported as a routing error instead of the
        authentication failure it is.
        """
        reasons = request.get_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS)
        check_path = self._options.check_path
        if not self._http_utils.check_request_path(request, check_path):
            if isinstance(reasons, UnsupportedReasons):
                reasons.add(
                    f'the request path "{request.get_uri().get_path()}" does not match '
                    f'the "check_path" option "{check_path}"',
                )
            return False
        return True

    @override
    async def start(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError | None = None,
    ) -> ResponseInterface:
        """Send the caller to the provider to authenticate."""
        del error
        check_public_client(self._oidc_client, self._options, self._signature_verifier)
        return await self._authorization.build(request, self._session_of(request))

    @override
    async def start_re_authentication(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
    ) -> ResponseInterface:
        """Send the caller to the provider to authenticate again.

        "prompt=login" is what OIDC Core 1.0, Section 3.1.2.1 defines for
        this: the provider prompts the user for credentials again instead of
        answering from the session it already holds. The previous ID token
        goes along as "id_token_hint" so the provider knows which user is
        being re-authenticated rather than offering a picker.

        "prompt" is a SHOULD in the specification. Configure "max_age" as
        well if the provider has to be obliged rather than asked: that one
        the client verifies, so a provider ignoring it fails the "auth_time"
        check instead of quietly returning the stale authentication that was
        denied in the first place.
        """
        check_public_client(self._oidc_client, self._options, self._signature_verifier)
        forced_params: dict[str, str] = {"prompt": "login"}
        if token.has_attribute("oidc_id_token"):
            id_token = token.get_attribute("oidc_id_token")
            if isinstance(id_token, str):
                forced_params["id_token_hint"] = id_token
        return await self._authorization.build(
            request,
            self._session_of(request),
            forced_params,
        )

    @override
    async def authenticate(self, request: ServerRequestInterface) -> Passport:
        """Consume the callback: match the state, exchange the code, validate the token.

        The state is validated first — an unauthenticated request would
        otherwise get an attacker-supplied "error_description" stored in the
        session, through the exception the failure handler keeps there (the
        provider echoes the state back on errors too, as RFC 6749, Section
        4.1.2.1 requires) — and the matched attempt is consumed right away,
        whatever the outcome: a replayed callback fails on the state check,
        and the other pending attempts survive.

        Raises:
            AuthenticationError: When any step of the callback fails.
        """
        check_public_client(self._oidc_client, self._options, self._signature_verifier)
        session = self._session_of(request)
        attempts = OidcLoginAttempts(session, self._options.firewall_name)
        response = read_callback(request)

        if response.state == "":
            raise AuthenticationError("Invalid OIDC state parameter.")
        attempt = await attempts.take(response.state)
        if attempt is None:
            # An unknown state fails with the same message as an empty
            # session: no oracle, no login CSRF.
            raise AuthenticationError("Invalid OIDC state parameter.")
        nonce = attempt.get("nonce")
        code_verifier = attempt.get("code_verifier")
        redirect_uri = attempt.get("redirect_uri")

        check_issuer(response.iss, await self._discovery.get_configuration())
        check_provider_error(response.error, response.error_description)

        if response.code == "":
            raise AuthenticationError("Missing authorization code in OIDC callback.")
        # The nonce is mandatory in this flow, since start() always sends
        # one: requiring it here means the check of the "nonce" claim in the
        # ID token can never be skipped.
        if not isinstance(nonce, str) or nonce == "":
            raise AuthenticationError("Missing OIDC nonce in session.")
        # Same for the PKCE verifier when PKCE is enabled: exchanging the
        # code without it would downgrade PKCE.
        if self._options.pkce_enabled and (
            not isinstance(code_verifier, str) or code_verifier == ""
        ):
            raise AuthenticationError("Missing PKCE code verifier in session.")
        # And the redirect URI resolved when the flow started: RFC 6749,
        # Section 4.1.3 requires the token request to carry the very value
        # the authorization request used, so it is replayed from the
        # attempt instead of being recomputed from the callback request,
        # whose host is not necessarily the one the flow started on.
        if not isinstance(redirect_uri, str) or redirect_uri == "":
            raise AuthenticationError("Missing OIDC redirect URI in session.")

        token_data = await self._oidc_client.exchange_code(
            response.code,
            redirect_uri,
            code_verifier if isinstance(code_verifier, str) else None,
        )
        id_token_value = token_data.get("id_token")
        if not isinstance(id_token_value, str) or id_token_value == "":
            raise AuthenticationError(
                'The token endpoint response does not contain a valid "id_token".',
            )
        access_token = token_data.get("access_token")
        if not isinstance(access_token, str) or access_token == "":
            raise AuthenticationError(
                'The token endpoint response does not contain a valid "access_token".',
            )

        # The signature is verified before the claims are read, so that a
        # token the provider did not issue never reaches the claim
        # validation at all.
        id_token_claims = (
            await self._signature_verifier.verify(id_token_value)
            if self._signature_verifier is not None
            else await self._id_token.decode(id_token_value)
        )
        self._id_token.validate_claims(
            id_token_claims,
            await self._discovery.get_issuer(),
            self._client_id,
            nonce,
            self._options.max_age,
        )

        claims = await fetch_user_claims(
            self._oidc_client, access_token, id_token_claims, self._options
        )
        return build_passport(
            claims, id_token_claims, token_data, self._user_provider, self._options
        )

    @override
    async def create_token(self, passport: Passport, firewall_name: str) -> TokenInterface:
        """Build the post-authentication token, carrying the OIDC tokens and proofs."""
        user = await passport.get_user()
        token = PostAuthenticationToken(user, firewall_name, user.get_roles())
        stamp_oidc_token(token, passport, self._clock)
        return token

    @override
    async def on_authentication_success(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
        firewall_name: str,
    ) -> ResponseInterface | None:
        """Drop every pending attempt, then let the success handler answer.

        Each pending attempt carries a nonce and a PKCE verifier, which have
        no place in an authenticated session; a callback for one of them
        would re-authenticate anyway, the state check just fails it earlier.
        """
        del firewall_name
        session = self._session_of(request)
        await OidcLoginAttempts(session, self._options.firewall_name).clear()
        return await self._success_handler.on_authentication_success(request, token)

    @override
    async def on_authentication_failure(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface:
        """Let the failure handler answer."""
        return await self._failure_handler.on_authentication_failure(request, error)

    @override
    def is_interactive(self) -> bool:
        """Announce the login as the user's own act: they followed the provider's round trip."""
        return True

    def _session_of(self, request: ServerRequestInterface) -> Session:
        """Return the session the request's security state carries.

        Raises:
            MissingSessionError: When the state carries none, which a
                stateless firewall or a session-less request would be.
        """
        session = parked_session_of(request)
        if session is None:
            raise MissingSessionError(
                'The "oidc_login" authenticator stores the OIDC "state", "nonce" and '
                "PKCE code verifier in the session, which this request has none of: it "
                "cannot be used with the session disabled, nor on a stateless firewall.",
            )
        return session
