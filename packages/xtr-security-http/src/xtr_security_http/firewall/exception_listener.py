"""The listener that turns a security error into a response on the lifecycle."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_http_foundation.session import (
    SessionInterface,
)
from xtr_http_kernel.bridge import (  # noqa: TC002 -- the container reads this constructor parameter's type at runtime
    StarletteHttpFactoryInterface,
)
from xtr_http_message_contracts.factory import (
    ResponseFactoryInterface,  # noqa: TC002 -- the container reads this constructor parameter's type at runtime
)
from xtr_logging_contracts import (
    LoggerInterface,  # noqa: TC002 -- the container reads this constructor parameter's type at runtime
)
from xtr_security_core.authentication.authentication_trust_resolver_interface import (  # noqa: TC002
    AuthenticationTrustResolverInterface,
)
from xtr_security_core.authentication.token.storage.token_storage_interface import (  # noqa: TC002
    TokenStorageInterface,
)
from xtr_security_core.exception import (
    AccessDeniedError,
    AccountStatusError,
    AuthenticationError,
    InsufficientAuthenticationError,
)

from xtr_security_http._security_state import SecurityState, security_state_of
from xtr_security_http.authorization.oauth2_scope_voter import parse_oauth2_scope
from xtr_security_http.entry_point.fallback_authentication_entry_point_interface import (
    FallbackAuthenticationEntryPointInterface,
)
from xtr_security_http.entry_point.re_authentication_entry_point_interface import (
    ReAuthenticationEntryPointInterface,
)
from xtr_security_http.exception import LogoutError
from xtr_security_http.security_request_attributes import SecurityRequestAttributes
from xtr_security_http.util.target_path import save_target_path

from ._exception_answers import ExceptionAnswers
from ._re_authentication import get_re_authentication_attribute, is_safe_method

if TYPE_CHECKING:
    from xtr_http_kernel import ExceptionEvent
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

    from xtr_security_http.authorization.access_denied_handler_interface import (
        AccessDeniedHandlerInterface,
    )
    from xtr_security_http.entry_point.authentication_entry_point_interface import (
        AuthenticationEntryPointInterface,
    )

__all__ = ["ExceptionListener"]

_XHR_HEADER: str = "x-requested-with"
"""The header a browser's XMLHttpRequest names itself with."""


@final
class ExceptionListener:
    """Turns a security error raised while handling a request into a response.

    One listener per firewall, built from that firewall's own parts — its
    name, its entry point, its access-denied handler — and parked by the
    firewall on the request's carrier, so a request's failure is answered by
    the firewall that ran it. The firewall's subscriber routes the request's
    failure here; a request no firewall matched is nobody's here, and its
    failure is the kernel's to answer.

    The failure is walked along its chain of causes: the first link that is
    one of this listener's is answered — an
    :class:`~xtr_security_core.exception.AuthenticationError` starts the
    entry point's challenge, an
    :class:`~xtr_security_core.exception.AccessDeniedError` is answered by
    denial, a :class:`~xtr_security_http.exception.LogoutError` — a logout
    that failed its proof — by a plain refusal. The one later link of the
    upstream order — a lazy response waiting for the response phase — has no
    local shape: the lazy-response decision is P2.10's to record, so its
    branch here is vacant until then.

    An authentication error starts the entry point's challenge, keeping the
    path the request was heading for on the session — unless the firewall is
    stateless, or the entry point only stands in and starts no authentication
    — and clearing the token when the error is an account-status one, so a
    disabled account cannot loop its own challenge. A firewall with no entry
    point answers a bare ``401``.

    A denial from a caller who is not fully authenticated is really an
    authentication gap: the entry point is started with an
    :class:`~xtr_security_core.exception.InsufficientAuthenticationError` —
    naming the masked authentication error the manager parked, when one was,
    so the challenge answers what actually failed. A denial from a fully
    authenticated caller is a refusal: a re-authentication entry point may
    answer a recency refusal with a fresh proof of the caller it holds;
    otherwise the firewall's scope handler answers a scope shortfall, its
    access-denied handler a configured refusal, and a plain ``403`` is the
    last word.

    The upstream error page — a sub-request rendering a denial — has no local
    counterpart: this kernel has no sub-request mechanism, so the
    ``error_page`` parameter is taken and kept for the surface that will
    carry it, and the branch is vacant: the refusal chain falls through to
    the plain ``403``. Recorded as a deviation for the error-page work.

    A response that already is what the framework sends — the kernel's own
    dual response, a message and a framework response at once — is set on
    the event as it is; a pure message is converted through the bridge first,
    which is the kernel's rule for messages from elsewhere.
    """

    __slots__ = (
        "_access_denied_handler",
        "_answers",
        "_entry_point",
        "_error_page",
        "_firewall_name",
        "_logger",
        "_re_authentication_entry_point",
        "_scope_denied_handler",
        "_stateless",
        "_token_storage",
        "_trust_resolver",
    )

    def __init__(  # noqa: PLR0913, PLR0917 -- the per-firewall shape: one listener built from its firewall's parts
        self,
        token_storage: TokenStorageInterface,
        trust_resolver: AuthenticationTrustResolverInterface,
        responses: ResponseFactoryInterface,
        bridge: StarletteHttpFactoryInterface,
        firewall_name: str,
        entry_point: AuthenticationEntryPointInterface | None = None,
        error_page: str | None = None,
        access_denied_handler: AccessDeniedHandlerInterface | None = None,
        scope_denied_handler: AccessDeniedHandlerInterface | None = None,
        logger: LoggerInterface | None = None,
        stateless: bool = True,
        re_authentication_entry_point: ReAuthenticationEntryPointInterface | None = None,
    ) -> None:
        """Build the listener from one firewall's parts.

        Args:
            token_storage: The request's token storage, cleared when an
                account-status error must not loop its own challenge.
            trust_resolver: Weighs the token the firewall authenticated.
            responses: Builds the bare ``401``/``403`` answers, so the
                listener names no response class.
            bridge: Turns a handler's pure message response into one the
                lifecycle's event accepts.
            firewall_name: The firewall this listener answers for, and whose
                name keys the target path on the session.
            entry_point: Answers an unauthenticated request with a challenge,
                or ``None`` for a bare ``401``.
            error_page: Kept for the error-page surface; vacant — this
                kernel has no sub-request mechanism, so a configured page is
                not rendered and the refusal chain falls through to ``403``.
            access_denied_handler: Answers a denied, fully authenticated
                caller, or ``None`` for a plain refusal.
            scope_denied_handler: Answers a denied OAuth2 scope with its own
                challenge, ahead of the plain access-denied handler.
            logger: Logs the branches as they are taken, when one is given.
            stateless: Whether the firewall keeps no session; a stateless
                firewall keeps no target path.
            re_authentication_entry_point: Starts a fresh proof for a caller
                who is already authenticated, or ``None`` while no surface
                configures one.
        """
        self._token_storage = token_storage
        self._trust_resolver = trust_resolver
        self._answers = ExceptionAnswers(responses, bridge)
        self._firewall_name = firewall_name
        self._entry_point = entry_point
        self._error_page = error_page
        self._access_denied_handler = access_denied_handler
        self._scope_denied_handler = scope_denied_handler
        self._logger = logger
        self._stateless = stateless
        self._re_authentication_entry_point = re_authentication_entry_point

    async def on_exception(self, event: ExceptionEvent) -> None:
        """Answer the request when the failure, or one of its causes, is one this listener owns.

        The chain of causes is walked first-link-first: the earliest security
        error in the chain is the one that decided the request's fate, so it
        is the one answered. A failure that is none of this listener's — and
        whose causes are none either — is left to whatever else handles it.
        """
        state = security_state_of(event.state)
        error: BaseException | None = event.exception
        while error is not None:
            if isinstance(error, AuthenticationError):
                answered = await self._handle_authentication_error(state, event.request, error)
                await self._answers.set_on(event, answered)
                return
            if isinstance(error, AccessDeniedError):
                answered = await self._handle_access_denied(state, event.request, error)
                await self._answers.set_on(event, answered)
                return
            if isinstance(error, LogoutError):
                answered = await self._handle_logout_error(error)
                await self._answers.set_on(event, answered)
                return
            # The upstream order holds one more link here: a lazy response
            # waiting for the response phase (P2.10's decision to record).
            # No local shape exists for it yet, so the branch has nothing
            # to walk.
            error = error.__cause__

    async def _handle_authentication_error(
        self,
        state: SecurityState,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface:
        """Start the entry point's challenge for an authentication error."""
        self._info(
            "An authentication error was thrown; starting the entry point.",
            {"firewall": self._firewall_name, "error": type(error).__name__},
        )
        return await self._start_authentication(state, request, error)

    async def _start_authentication(
        self,
        state: SecurityState,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface:
        """Answer ``error`` with the entry point's challenge, or a bare ``401``.

        The path the request was heading for is kept on the session — unless
        the firewall is stateless, or the entry point only stands in and
        starts no authentication, so there is nothing to come back to. An
        account-status error clears the token first: a disabled or expired
        account must not loop its own challenge.
        """
        if self._entry_point is None:
            self._notice(
                "No entry point configured; answering a bare 401.",
                {"firewall": self._firewall_name},
            )
            return await self._answers.bare_challenge()
        if not self._stateless and not isinstance(
            self._entry_point, FallbackAuthenticationEntryPointInterface
        ):
            await self._save_target_path(state, request)
        if isinstance(error, AccountStatusError):
            self._token_storage.set_token(None)
            state.token = None
            self._info(
                "The token was removed for an account-status error.",
                {"firewall": self._firewall_name, "error": type(error).__name__},
            )
        return await self._entry_point.start(request, error)

    async def _handle_logout_error(self, error: LogoutError) -> ResponseInterface:
        """Refuse a logout that failed its proof.

        A logout that did not prove itself is not answered with a challenge —
        the caller may well be authenticated — nor with a page explaining a
        denial: it is refused, the way a request that failed a proof of the
        application's own is.
        """
        self._info(
            "A logout error was thrown; refusing the request.",
            {"firewall": self._firewall_name, "error": type(error).__name__},
        )
        return await self._answers.forbidden()

    async def _handle_access_denied(
        self,
        state: SecurityState,
        request: ServerRequestInterface,
        error: AccessDeniedError,
    ) -> ResponseInterface:
        """Answer a denial: a challenge when not fully authenticated, else a refusal.

        A caller the trust resolver weighs full-fledged — or remembered, so
        known — may be asked for a fresh proof instead of refused, when a
        vote that denied a single attribute asked for one and an entry point
        exists that starts one. Otherwise a caller who is not full-fledged is
        really missing authentication, and the entry point is started for
        them; a full-fledged caller is refused: the scope handler, the
        access-denied handler, the plain ``403``.
        """
        # A step that decides against the token parks it on the state; the
        # switch step runs before the access step that parks it, so a
        # switch's denial weighs the token the storage restored — the same
        # token the switch decided against — when no step parked one yet.
        token = state.token if state.token is not None else self._token_storage.get_token()
        full_fledged = self._trust_resolver.is_full_fledged(token)
        re_authentication = self._re_authentication_entry_point
        if re_authentication is None and isinstance(
            self._entry_point, ReAuthenticationEntryPointInterface
        ):
            re_authentication = self._entry_point
        attribute = get_re_authentication_attribute(error)
        if (
            token is not None
            and (full_fledged or self._trust_resolver.is_remember_me(token))
            and re_authentication is not None
            and attribute is not None
        ):
            self._debug(
                "Starting a re-authentication for an attribute.",
                {"firewall": self._firewall_name, "attribute": attribute},
            )
            if not self._stateless:
                await self._save_target_path(state, request)
            asked = request.with_attribute(
                SecurityRequestAttributes.RE_AUTHENTICATION_ATTRIBUTE, attribute
            )
            return await re_authentication.start_re_authentication(asked, token)
        if not full_fledged:
            self._debug(
                "Access denied; the caller is not fully authenticated, starting the entry point.",
                {"firewall": self._firewall_name},
            )
            parked = state.attributes.get(SecurityRequestAttributes.AUTHENTICATION_ERROR)
            failed = parked if isinstance(parked, AuthenticationError) else None
            insufficient = InsufficientAuthenticationError()
            return await self._start_authentication(
                state,
                request,
                failed if failed is not None else insufficient,
            )
        self._debug(
            "Access denied; the caller is fully authenticated and not asked to re-authenticate.",
            {"firewall": self._firewall_name},
        )
        if self._scope_denied_handler is not None and _is_scope_denial(error):
            answered = await self._scope_denied_handler.handle(request, error)
            if answered is not None:
                return answered
        if self._access_denied_handler is not None:
            answered = await self._access_denied_handler.handle(request, error)
            if answered is not None:
                return answered
        # The upstream refusal chain holds one more link here: the error
        # page, answered by a sub-request. This kernel has no sub-request
        # mechanism, so a configured ``error_page`` is not rendered and the
        # chain falls through to the plain refusal.
        return await self._answers.forbidden()

    async def _save_target_path(
        self,
        state: SecurityState,
        request: ServerRequestInterface,
    ) -> None:
        """Keep the URI ``request`` was heading for, for the return trip.

        Only when the request carries a session, arrived by a safe method —
        one that changed nothing, so returning to it is returning to the same
        request — and is not a browser's background XMLHttpRequest, whose
        return trip is the script's own.
        """
        session = state.attributes.get(SecurityRequestAttributes.SESSION)
        if (
            isinstance(session, SessionInterface)
            and is_safe_method(request.get_method())
            and request.get_header_line(_XHR_HEADER) != "XMLHttpRequest"
        ):
            await save_target_path(session, self._firewall_name, str(request.get_uri()))

    def _debug(self, message: str, context: dict[str, object]) -> None:
        """Log ``message`` at debug level, when a logger was given."""
        if self._logger is not None:
            self._logger.debug(message, context)

    def _info(self, message: str, context: dict[str, object]) -> None:
        """Log ``message`` at info level, when a logger was given."""
        if self._logger is not None:
            self._logger.info(message, context)

    def _notice(self, message: str, context: dict[str, object]) -> None:
        """Log ``message`` at notice level, when a logger was given."""
        if self._logger is not None:
            self._logger.notice(message, context)


def _is_scope_denial(error: AccessDeniedError) -> bool:
    """Tell whether the denied attribute is an OAuth2 scope request."""
    return any(parse_oauth2_scope(attribute) is not None for attribute in error.attributes)
