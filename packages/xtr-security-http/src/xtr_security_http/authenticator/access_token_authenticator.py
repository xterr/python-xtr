"""The authenticator that proves a caller by a bearer access token."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, cast, final

from starlette.responses import JSONResponse
from typing_extensions import override
from xtr_security_core.exception import AuthenticationError, BadCredentialsError

from xtr_security_http._challenge import no_store_headers, quote_auth_param
from xtr_security_http.authenticator.passport.self_validating_passport import SelfValidatingPassport
from xtr_security_http.authorization.oauth2_scope_voter import OAuth2ScopeVoter
from xtr_security_http.entry_point.authentication_entry_point_interface import (
    AuthenticationEntryPointInterface,
)
from xtr_security_http.exception.invalid_access_token_error import InvalidAccessTokenError

from .abstract_authenticator import AbstractAuthenticator

if TYPE_CHECKING:
    from collections.abc import Iterable

    from starlette.requests import Request
    from starlette.responses import Response
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface
    from xtr_security_core.user.user_provider_interface import UserProviderInterface

    from xtr_security_http.access_token.access_token_extractor_interface import (
        AccessTokenExtractorInterface,
    )
    from xtr_security_http.access_token.access_token_handler_interface import (
        AccessTokenHandlerInterface,
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
class AccessTokenAuthenticator(AbstractAuthenticator, AuthenticationEntryPointInterface):
    """Authenticates a request by a bearer access token, and challenges when it is absent or bad.

    An extractor reads the token out of the request; a handler validates it and
    returns a user badge. The passport is self-validating — the token already
    proved the user — so no credentials are checked. The badge's ``scope``
    attribute (a list, or a space-separated string) becomes the token's
    ``oauth2_scope`` attribute, the one
    :class:`~xtr_security_http.authorization.oauth2_scope_voter.OAuth2ScopeVoter`
    reads.

    As the firewall's entry point it also answers an unauthenticated or failed
    request with the RFC 6750 ``WWW-Authenticate: Bearer`` challenge — a bare
    one when no token was sent, ``error="invalid_token"`` when one was rejected.

    Attributes:
        realm: The protection realm named in the challenge, when set.
    """

    #: The token attribute the copied scopes are stored under.
    SCOPE_ATTRIBUTE: ClassVar[str] = OAuth2ScopeVoter.SCOPE_ATTRIBUTE

    #: The badge attribute the handler stores the granted scopes under.
    BADGE_SCOPE_ATTRIBUTE: ClassVar[str] = "scope"

    __slots__: ClassVar[tuple[str, ...]] = (
        "_extractor",
        "_failure_handler",
        "_handler",
        "_realm",
        "_success_handler",
        "_user_provider",
    )

    def __init__(  # noqa: PLR0913, PLR0917 -- a wiring constructor; the handlers are optional peers
        self,
        handler: AccessTokenHandlerInterface,
        extractor: AccessTokenExtractorInterface,
        user_provider: UserProviderInterface | None = None,
        success_handler: AuthenticationSuccessHandlerInterface | None = None,
        failure_handler: AuthenticationFailureHandlerInterface | None = None,
        realm: str | None = None,
    ) -> None:
        """Record the handler, extractor, optional provider, handlers and realm."""
        self._handler = handler
        self._extractor = extractor
        self._user_provider = user_provider
        self._success_handler = success_handler
        self._failure_handler = failure_handler
        self._realm = realm

    @property
    def extractor(self) -> AccessTokenExtractorInterface:
        """Return the extractor that reads the token out of a request."""
        return self._extractor

    @override
    def supports(self, request: Request) -> bool | None:
        """Handle the request only when it carries a token this extractor reads.

        Returns ``None`` — not ``False`` — when no token is present, so the
        firewall leaves the request anonymous rather than failing it; a
        protected route then challenges through the entry point.
        """
        del request
        return None

    @override
    async def authenticate(self, request: Request) -> Passport:
        """Read and validate the token, and build a self-validating passport.

        Raises:
            AuthenticationError: When no token is present, or the handler
                rejects the one that is.
        """
        token = await self._extractor.extract_access_token(request)
        if token is None:
            raise BadCredentialsError("No access token was found in the request.")
        badge = await self._handler.get_user_badge_from(token)
        if self._user_provider is not None and badge.get_user_loader() is None:
            provider = self._user_provider

            async def load(identifier: str) -> UserInterface:
                return await provider.load_user_by_identifier(identifier)

            badge.set_user_loader(load)
        passport = SelfValidatingPassport(badge)
        scope = badge.get_attributes().get(self.BADGE_SCOPE_ATTRIBUTE)
        if scope is not None:
            passport.set_attribute(self.SCOPE_ATTRIBUTE, scope)
        return passport

    @override
    async def create_token(self, passport: Passport, firewall_name: str) -> TokenInterface:
        """Build the token and copy the passport's scope onto it as ``oauth2_scope``."""
        token = await super().create_token(passport, firewall_name)
        scope = passport.get_attribute(self.SCOPE_ATTRIBUTE)
        if scope is not None:
            token.set_attribute(self.SCOPE_ATTRIBUTE, self._normalize_scope(scope))
        return token

    @override
    async def on_authentication_success(
        self,
        request: Request,
        token: TokenInterface,
        firewall_name: str,
    ) -> Response | None:
        """Delegate to the success handler, or let the request go on."""
        if self._success_handler is not None:
            return await self._success_handler.on_authentication_success(
                request,
                token,
                firewall_name,
            )
        return None

    @override
    async def on_authentication_failure(
        self,
        request: Request,
        error: AuthenticationError,
    ) -> Response | None:
        """Delegate to the failure handler, or let the entry point challenge."""
        if self._failure_handler is not None:
            return await self._failure_handler.on_authentication_failure(request, error)
        return None

    @override
    async def start(self, request: Request, error: AuthenticationError | None = None) -> Response:
        """Answer an unauthenticated or failed request with an RFC 6750 challenge.

        A rejected token — an
        :class:`InvalidAccessTokenError` — draws the
        ``error="invalid_token"`` challenge and a matching body; a request that
        carried no token, or one only lacking authentication, draws a bare
        ``Bearer`` challenge.
        """
        del request
        parts = ["Bearer"]
        if self._realm is not None:
            parts.append(f"realm={quote_auth_param(self._realm)}")
        body: dict[str, str] = {}
        if isinstance(error, InvalidAccessTokenError):
            parts.append('error="invalid_token"')
            parts.append(f"error_description={quote_auth_param(error.get_message_key())}")
            body = {"error": "invalid_token"}
        challenge = parts[0] + (" " + ", ".join(parts[1:]) if len(parts) > 1 else "")
        return JSONResponse(
            body,
            status_code=401,
            headers=no_store_headers(**{"WWW-Authenticate": challenge}),
        )

    def _normalize_scope(self, scope: object) -> list[str]:
        """Turn a scope list or space-separated string into a list of scopes."""
        if isinstance(scope, str):
            return scope.split()
        if isinstance(scope, (list, tuple, set, frozenset)):
            items: Iterable[object] = cast("Iterable[object]", scope)
            return [str(one) for one in items]
        return [str(scope)]
