"""The authenticator that proves a caller by a bearer access token."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final

from typing_extensions import override
from xtr_http_message_contracts.factory import (
    ResponseFactoryInterface,  # noqa: TC002 -- the container reads this constructor parameter's type at runtime
)
from xtr_security_core.exception import AuthenticationError, BadCredentialsError

from xtr_security_http._challenge import json_challenge
from xtr_security_http.authenticator._access_token_challenge import (
    access_token_challenge,
)
from xtr_security_http.authenticator._access_token_scopes import extract_scopes, normalize_scope
from xtr_security_http.authenticator.fallback_user_loader import FallbackUserLoader
from xtr_security_http.authenticator.passport.self_validating_passport import SelfValidatingPassport
from xtr_security_http.authorization.oauth2_scope_voter import OAuth2ScopeVoter
from xtr_security_http.entry_point.fallback_authentication_entry_point_interface import (
    FallbackAuthenticationEntryPointInterface,
)

from .abstract_authenticator import AbstractAuthenticator

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface
    from xtr_security_core.user.user_provider_interface import UserProviderInterface

    from xtr_security_http.access_token.access_token_extractor_interface import (
        AccessTokenExtractorInterface,
    )
    from xtr_security_http.access_token.access_token_handler_interface import (
        AccessTokenHandlerInterface,
    )
    from xtr_security_http.access_token.sender_constraint_interface import (
        SenderConstraintInterface,
    )
    from xtr_security_http.authentication.authentication_failure_handler_interface import (
        AuthenticationFailureHandlerInterface,
    )
    from xtr_security_http.authentication.authentication_success_handler_interface import (
        AuthenticationSuccessHandlerInterface,
    )
    from xtr_security_http.authenticator.passport.passport import Passport

__all__ = ["AccessTokenAuthenticator"]


@final
class AccessTokenAuthenticator(
    AbstractAuthenticator,
    FallbackAuthenticationEntryPointInterface,
):
    """Authenticates a request by a bearer access token, and challenges when it is absent or bad.

    An extractor reads the token out of the request; a handler validates it and
    returns a user badge. The passport is self-validating — the token already
    proved the user — so no credentials are checked. The granted scopes,
    read from the badge's ``scope`` or ``scp`` attribute, become the token's
    ``oauth2_scope`` attribute, the one
    :class:`~xtr_security_http.authorization.oauth2_scope_voter.OAuth2ScopeVoter`
    reads. A sender constraint, when one is configured, checks the request
    against what the token says it is bound to before anything is loaded on
    the user's behalf, and its scheme and parameters are the challenge's.

    A failed authentication is always answered here: a ``401`` whose
    ``WWW-Authenticate`` names ``invalid_token`` and says why. As the
    firewall's stand-in entry point it also answers an unauthenticated
    request with the RFC 6750 challenge that carries no error code — an
    error code describes a token the client did send; it only stands in, so
    a firewall holding an entry point that starts an authentication keeps
    that one.

    Attributes:
        realm: The protection realm named in the challenge, when set.
    """

    #: The token attribute the copied scopes are stored under.
    SCOPE_ATTRIBUTE: ClassVar[str] = OAuth2ScopeVoter.SCOPE_ATTRIBUTE

    #: The badge attributes a scope is read from, in order of precedence:
    #: ``scope`` is the one RFC 9068 Section 2.2.3 and RFC 7662 Section 2.2
    #: define, ``scp`` the spelling some providers use instead.
    SCOPE_CLAIMS: ClassVar[tuple[str, ...]] = ("scope", "scp")

    __slots__: tuple[str, ...] = (
        "_extractor",
        "_failure_handler",
        "_handler",
        "_realm",
        "_resource_metadata_uri",
        "_responses",
        "_sender_constraint",
        "_success_handler",
        "_user_provider",
    )

    def __init__(  # noqa: PLR0913, PLR0917 -- a wiring constructor; the handlers and peers are optional
        self,
        handler: AccessTokenHandlerInterface,
        extractor: AccessTokenExtractorInterface,
        responses: ResponseFactoryInterface,
        user_provider: UserProviderInterface | None = None,
        success_handler: AuthenticationSuccessHandlerInterface | None = None,
        failure_handler: AuthenticationFailureHandlerInterface | None = None,
        realm: str | None = None,
        resource_metadata_uri: str | None = None,
        sender_constraint: SenderConstraintInterface | None = None,
    ) -> None:
        """Record the handler, extractor, response factory, optional peers and challenge settings.

        Args:
            handler: Validates a token into a user badge.
            extractor: Reads the token out of a request.
            responses: Builds the challenge responses the entry point answers
                with, so the authenticator names no response class.
            user_provider: Loads the user an identifier names, when the badge
                the handler returned carries no loader of its own — or one
                marked as a stand-in.
            success_handler: Reacts to a successful authentication, or ``None``.
            failure_handler: Reacts to a failed authentication, or ``None``.
            realm: The protection realm named in the challenge, or ``None``.
            resource_metadata_uri: The RFC 9728 protected-resource metadata
                URL the challenge advertises; a path is resolved against the
                request.
            sender_constraint: What the request has to prove possession of,
                beyond holding the access token, for it to be accepted;
                ``None`` accepts a token from whoever presents it, which is
                what a bearer token is (RFC 6750, Section 1).
        """
        self._handler = handler
        self._extractor = extractor
        self._responses = responses
        self._user_provider = user_provider
        self._success_handler = success_handler
        self._failure_handler = failure_handler
        self._realm = realm
        self._resource_metadata_uri = resource_metadata_uri
        self._sender_constraint = sender_constraint

    @property
    def extractor(self) -> AccessTokenExtractorInterface:
        """Return the extractor that reads the token out of a request."""
        return self._extractor

    @override
    def supports(self, request: ServerRequestInterface) -> bool | None:
        """Answer lazily: ``None``, whether or not the request carries a token.

        Upstream answers ``False`` when its extractor finds no token,
        collecting the reason; the local extractor's read is async and this
        hook is sync, so the miss is answered one step later instead —
        ``authenticate`` raises the no-token error and the manager's lazy
        abstain skips this authenticator, leaving the request anonymous
        exactly as a ``False`` would.
        """
        del request
        return None

    @override
    async def authenticate(self, request: ServerRequestInterface) -> Passport:
        """Read and validate the token, and build a self-validating passport.

        The sender constraint, when one is configured, weighs the request
        against what the token says it is bound to before anything is loaded
        on the user's behalf.

        Raises:
            AuthenticationError: When no token is present, the handler
                rejects the one that is, or the request does not prove
                possession of what the token is bound to.
        """
        token = await self._extractor.extract_access_token(request)
        if token is None:
            raise BadCredentialsError("No access token was found in the request.")
        badge = await self._handler.get_user_badge_from(token)
        if self._sender_constraint is not None:
            await self._sender_constraint.check(request, token, badge.get_attributes())
        if self._user_provider is not None:
            loader = badge.get_user_loader()
            if loader is None or isinstance(  # pyright: ignore[reportUnnecessaryIsInstance] -- the loader's declared type is the callable union; a stand-in wrapper is one callable spelling of it
                loader,
                FallbackUserLoader,
            ):
                provider = self._user_provider

                async def load(identifier: str) -> UserInterface:
                    return await provider.load_user_by_identifier(identifier)

                badge.set_user_loader(load)
        passport = SelfValidatingPassport(badge)
        scopes = extract_scopes(badge.get_attributes(), self.SCOPE_CLAIMS)
        if scopes:
            passport.set_attribute(self.SCOPE_ATTRIBUTE, scopes)
        return passport

    @override
    async def create_token(self, passport: Passport, firewall_name: str) -> TokenInterface:
        """Build the token and copy the passport's scope onto it as ``oauth2_scope``."""
        token = await super().create_token(passport, firewall_name)
        scope = passport.get_attribute(self.SCOPE_ATTRIBUTE)
        if scope is not None:
            token.set_attribute(self.SCOPE_ATTRIBUTE, normalize_scope(scope))
        return token

    @override
    async def on_authentication_success(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
        firewall_name: str,
    ) -> ResponseInterface | None:
        """Delegate to the success handler, or let the request go on."""
        del firewall_name  # the handler answers without it; the hook keeps the upstream shape
        if self._success_handler is not None:
            return await self._success_handler.on_authentication_success(request, token)
        return None

    @override
    async def on_authentication_failure(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface:
        """Answer the failure: the handler's response, or the ``invalid_token`` challenge.

        A configured failure handler answers for this authenticator. Without
        one the failure is answered here and now — a ``401`` naming
        ``invalid_token`` and saying why — so a refused token is told it was
        refused, rather than waiting for the access decision to challenge an
        anonymous request.
        """
        if self._failure_handler is not None:
            return await self._failure_handler.on_authentication_failure(request, error)
        return await json_challenge(
            self._responses,
            401,
            {"error": "invalid_token"},
            {
                "WWW-Authenticate": access_token_challenge(
                    request,
                    error_code="invalid_token",
                    error_description=error.get_message_key(),
                    error=error,
                    realm=self._realm,
                    resource_metadata_uri=self._resource_metadata_uri,
                    sender_constraint=self._sender_constraint,
                ),
            },
        )

    @override
    async def start(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError | None = None,
    ) -> ResponseInterface:
        """Answer an unauthenticated request with the RFC 6750 challenge.

        The challenge of a request that carried no token at all holds no
        error code — an error code describes a token the client did send —
        so this is the bare challenge through which an RFC 9728 client
        discovers where to get a token from. A token that was rejected is
        the failure hook's to answer, with ``invalid_token``.
        """
        return await json_challenge(
            self._responses,
            401,
            {},
            {
                "WWW-Authenticate": access_token_challenge(
                    request,
                    realm=self._realm,
                    resource_metadata_uri=self._resource_metadata_uri,
                    sender_constraint=self._sender_constraint,
                    error_code=None,
                    error_description=None,
                    error=error,
                ),
            },
        )
