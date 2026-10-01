"""Drives a firewall's authenticators over one request, in the fixed order."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_security_core.event.authentication_success_event import AuthenticationSuccessEvent
from xtr_security_core.exception import AuthenticationError, BadCredentialsError

from xtr_security_http.authentication._sensitive import mask
from xtr_security_http.authentication.expose_security_level import ExposeSecurityLevel
from xtr_security_http.event.authentication_token_created_event import (
    AuthenticationTokenCreatedEvent,
)
from xtr_security_http.event.check_passport_event import CheckPassportEvent
from xtr_security_http.event.login_failure_event import LoginFailureEvent
from xtr_security_http.event.login_success_event import LoginSuccessEvent

from .authenticator_manager_interface import AuthenticatorManagerInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from starlette.requests import Request
    from starlette.responses import Response
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_security_core.authentication.token.storage.token_storage_interface import (
        TokenStorageInterface,
    )
    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from xtr_security_http.authenticator.authenticator_interface import AuthenticatorInterface
    from xtr_security_http.authenticator.passport.badge.badge_interface import BadgeInterface
    from xtr_security_http.authenticator.passport.passport import Passport

__all__ = ["AuthenticatorManager"]

#: Returned when a lazy authenticator did not apply — no credential was presented.
_ABSTAINED: object = object()


@final
class AuthenticatorManager(AuthenticatorManagerInterface):
    """Runs the authenticators of one firewall and dispatches the events around each step.

    The order is fixed and is the whole contract of this class:

    1. the first authenticator whose :meth:`supports` is not ``False`` reads
       the request into a passport;
    2. a :class:`~xtr_security_http.event.check_passport_event.CheckPassportEvent`
       lets listeners resolve the badges — set the user loader, verify a
       password;
    3. every badge must report itself resolved, and every required badge must
       be present, or a
       :class:`~xtr_security_core.exception.BadCredentialsError` is raised;
    4. the user is loaded and a token is created, then an
       :class:`~xtr_security_http.event.authentication_token_created_event.AuthenticationTokenCreatedEvent`
       lets a listener replace it;
    5. an
       :class:`~xtr_security_core.event.authentication_success_event.AuthenticationSuccessEvent`
       runs the post-authentication account check;
    6. the token is stored, the authenticator's success handler runs, and a
       :class:`~xtr_security_http.event.login_success_event.LoginSuccessEvent`
       lets a listener migrate a password or replace the response.

    A failure anywhere is masked to the configured level, announced as a
    :class:`~xtr_security_http.event.login_failure_event.LoginFailureEvent`,
    offered to the authenticator's failure handler, and — if nobody answered —
    re-raised for the firewall's entry point to turn into a challenge.
    """

    __slots__ = (
        "_authenticators",
        "_event_dispatcher",
        "_expose_security_errors",
        "_firewall_name",
        "_logger",
        "_required_badges",
        "_token_storage",
    )

    def __init__(  # noqa: PLR0913, PLR0917 -- a wiring constructor; every dependency is required
        self,
        authenticators: Sequence[AuthenticatorInterface],
        token_storage: TokenStorageInterface,
        event_dispatcher: EventDispatcherInterface,
        firewall_name: str,
        logger: LoggerInterface | None = None,
        expose_security_errors: ExposeSecurityLevel = ExposeSecurityLevel.NONE,
        required_badges: Sequence[type[BadgeInterface]] = (),
    ) -> None:
        """Record the authenticators, the storage, the dispatcher and the policy."""
        self._authenticators = tuple(authenticators)
        self._token_storage = token_storage
        self._event_dispatcher = event_dispatcher
        self._firewall_name = firewall_name
        self._logger = logger
        self._expose_security_errors = expose_security_errors
        self._required_badges = tuple(required_badges)

    @override
    def supports(self, request: Request) -> bool | None:
        """Tell whether an authenticator handles ``request``: ``True``, ``None`` or ``False``."""
        lazy = False
        for authenticator in self._authenticators:
            supported = authenticator.supports(request)
            if supported is True:
                return True
            if supported is None:
                lazy = True
        return None if lazy else False

    @override
    async def authenticate_request(self, request: Request) -> Response | None:
        """Authenticate ``request`` through the first supporting authenticator.

        A lazy authenticator — one whose :meth:`supports` returned ``None`` —
        that raises a plain
        :class:`~xtr_security_core.exception.BadCredentialsError` is read as "no
        credential presented": it did not apply, so the next authenticator is
        tried and, failing that, the request stays anonymous. Any other failure
        from it, and every failure from an eager authenticator, is a real
        authentication failure the firewall turns into a challenge.
        """
        for authenticator in self._authenticators:
            supported = authenticator.supports(request)
            if supported is False:
                continue
            outcome = await self._authenticate(authenticator, request, lazy=supported is None)
            if outcome is not _ABSTAINED:
                return cast("Response | None", outcome)
        return None

    async def _authenticate(
        self,
        authenticator: AuthenticatorInterface,
        request: Request,
        *,
        lazy: bool,
    ) -> Response | object | None:
        """Carry one authenticator through the sequence, or abstain when it does not apply."""
        passport: Passport | None = None
        try:
            passport = await authenticator.authenticate(request)
            _ = await self._event_dispatcher.dispatch(CheckPassportEvent(authenticator, passport))
            self._ensure_resolved(passport)
            _ = await passport.get_user()
            token = await authenticator.create_token(passport, self._firewall_name)
            token = await self._token_created(token, passport)
            _ = await self._event_dispatcher.dispatch(AuthenticationSuccessEvent(token))
        except BadCredentialsError as error:
            if lazy and passport is None:
                return _ABSTAINED
            return await self._on_failure(authenticator, request, passport, error)
        except AuthenticationError as error:
            return await self._on_failure(authenticator, request, passport, error)
        return await self._on_success(authenticator, request, passport, token)

    def _ensure_resolved(self, passport: Passport) -> None:
        """Raise when a badge is unresolved or a required badge is absent."""
        passport.check_if_completely_resolved()
        for badge in self._required_badges:
            if not passport.has_badge(badge):
                raise BadCredentialsError(
                    f"The passport is missing the required badge {badge.__name__}.",
                )

    async def _token_created(self, token: TokenInterface, passport: Passport) -> TokenInterface:
        """Announce the created token and return whichever token a listener settled on."""
        event = AuthenticationTokenCreatedEvent(token, passport)
        _ = await self._event_dispatcher.dispatch(event)
        return event.get_authenticated_token()

    async def _on_success(
        self,
        authenticator: AuthenticatorInterface,
        request: Request,
        passport: Passport,
        token: TokenInterface,
    ) -> Response | None:
        """Store the token, run the success handler, then announce the login."""
        self._token_storage.set_token(token)
        if self._logger is not None:
            self._logger.info(
                "Authenticated the request.",
                {"firewall": self._firewall_name, "user": token.get_user_identifier()},
            )
        response = await authenticator.on_authentication_success(
            request,
            token,
            self._firewall_name,
        )
        event = LoginSuccessEvent(
            authenticator,
            passport,
            token,
            request,
            response,
            self._firewall_name,
        )
        _ = await self._event_dispatcher.dispatch(event)
        return event.get_response()

    async def _on_failure(
        self,
        authenticator: AuthenticatorInterface,
        request: Request,
        passport: Passport | None,
        error: AuthenticationError,
    ) -> Response | None:
        """Mask the error, announce the failure, offer it to the handler, then re-raise.

        Raises:
            AuthenticationError: The masked error, when no listener or handler
                answered it — the firewall turns it into a challenge.
        """
        masked = mask(error, self._expose_security_errors)
        if self._logger is not None:
            self._logger.info(
                "Authentication failed.",
                {"firewall": self._firewall_name, "error": type(error).__name__},
            )
        event = LoginFailureEvent(masked, authenticator, request, passport, self._firewall_name)
        _ = await self._event_dispatcher.dispatch(event)
        if event.get_response() is not None:
            return event.get_response()
        response = await authenticator.on_authentication_failure(request, masked)
        if response is not None:
            return response
        raise masked
