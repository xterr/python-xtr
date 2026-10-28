"""Drives a firewall's authenticators over one request, in the fixed order."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_security_core.event.authentication_success_event import AuthenticationSuccessEvent
from xtr_security_core.exception import AuthenticationError, BadCredentialsError

from xtr_security_http.authentication.expose_security_level import ExposeSecurityLevel
from xtr_security_http.authentication.user_authenticator_interface import UserAuthenticatorInterface
from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.self_validating_passport import SelfValidatingPassport
from xtr_security_http.event.authentication_token_created_event import (
    AuthenticationTokenCreatedEvent,
)
from xtr_security_http.event.check_passport_event import CheckPassportEvent
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from ._authentication_outcome import AuthenticationOutcome, ManagerWiring
from ._manager_reporting import authenticator_name, log_debug, log_info
from ._supports_pass import run_supports_pass
from .authenticator_manager_interface import AuthenticatorManagerInterface

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_security_core.authentication.token.storage.token_storage_interface import (
        TokenStorageInterface,
    )
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface

    from xtr_security_http._security_state import SecurityState
    from xtr_security_http.authenticator.authenticator_interface import AuthenticatorInterface
    from xtr_security_http.authenticator.passport.badge.badge_interface import BadgeInterface
    from xtr_security_http.authenticator.passport.passport import Passport

__all__ = ["AuthenticatorManager"]

#: Returned when a lazy authenticator did not apply — no credential was presented.
_ABSTAINED: object = object()


@final
class AuthenticatorManager(AuthenticatorManagerInterface, UserAuthenticatorInterface):
    """Runs the authenticators of one firewall and dispatches the events around each step.

    The order is fixed and is the whole contract of this class:

    1. a supports pass asks every authenticator, parking the supporters and
        the skipped on the request's security state; the first supporter
        that still applies reads the request into a passport;
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
    6. the token is stored, the authenticator's success handler runs, an
        interactive authenticator announces the login through an
        :class:`~xtr_security_http.event.interactive_login_event.InteractiveLoginEvent`,
        and a
        :class:`~xtr_security_http.event.login_success_event.LoginSuccessEvent`
        lets a listener migrate a password or replace the response.

    A failure anywhere never raises: the error is masked to the configured
    level, the authenticator's failure handler runs, and a
    :class:`~xtr_security_http.event.login_failure_event.LoginFailureEvent`
    lets a listener answer the request. A response from any of them is
    returned for the firewall to send; the lack of one means the request goes
    on anonymous — the access decision is what turns that into a challenge.
    """

    __slots__ = (
        "_authenticators",
        "_event_dispatcher",
        "_expose_security_errors",
        "_firewall_name",
        "_logger",
        "_outcome",
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
        self._outcome = AuthenticationOutcome(
            ManagerWiring(
                token_storage,
                event_dispatcher,
                firewall_name,
                logger,
                expose_security_errors,
                tuple(required_badges),
            )
        )

    @override
    def supports(self, request: ServerRequestInterface, state: SecurityState) -> bool | None:
        """Tell whether an authenticator handles ``request``: ``True``, ``None`` or ``False``.

        Every authenticator is asked — the pass records the complete picture,
        parking the supporters and the skipped on ``state`` for the pass that
        authenticates, so none is asked twice within one pass. ``True`` means
        an authenticator definitely applies; ``None`` that only lazy ones do,
        none of them sure a credential is present; ``False`` that none
        applies.

        Raises:
            InvalidArgumentError: When one of the authenticators is no
                :class:`~xtr_security_http.authenticator.authenticator_interface.AuthenticatorInterface`
                — a wiring mistake, not a request failure.
        """
        skipped, supporters, lazy = run_supports_pass(
            self._authenticators, request, firewall_name=self._firewall_name, logger=self._logger
        )
        state.attributes[SecurityRequestAttributes.SKIPPED_AUTHENTICATORS] = skipped
        state.attributes[SecurityRequestAttributes.AUTHENTICATORS] = supporters
        if not supporters:
            return False
        return None if lazy else True

    @override
    async def authenticate_request(
        self,
        request: ServerRequestInterface,
        state: SecurityState,
    ) -> ResponseInterface | None:
        """Authenticate ``request`` through the supporters the supports pass recorded.

        The pass hands its findings over through ``state`` — read and removed
        here, once — so a second call over the same request finds nothing
        parked and leaves it anonymous. Nothing parked at all means no
        supports pass ran: the request stays anonymous too.

        A lazy authenticator — one whose :meth:`supports` returned ``None`` —
        that raises a plain
        :class:`~xtr_security_core.exception.BadCredentialsError` is read as "no
        credential presented": it did not apply, so the next authenticator is
        tried. Any other failure is a real one, handled without raising: the
        request goes on anonymous, and the access decision is what turns that
        into a challenge.
        """
        parked = state.attributes.pop(SecurityRequestAttributes.AUTHENTICATORS, None)
        _ = state.attributes.pop(SecurityRequestAttributes.SKIPPED_AUTHENTICATORS, None)
        if not parked:
            return None
        return await self.execute_authenticators(
            cast("tuple[AuthenticatorInterface, ...]", parked),
            request,
            state,
        )

    async def execute_authenticators(
        self,
        authenticators: Sequence[AuthenticatorInterface],
        request: ServerRequestInterface,
        state: SecurityState,
    ) -> ResponseInterface | None:
        """Run the handed-off authenticators in order, re-checking each first.

        The re-check is per authenticator — never the full supports pass
        again — because what the request carries may have changed between
        the pass and now. A re-check that turned ``False`` skips its
        authenticator with a note. Only a response ends the run — once one
        authenticator answered, no later one is called; an outcome of
        ``None``, from a success or a handled failure that answered nothing,
        lets the run go on to the next authenticator, and a lazy abstain
        (no credential presented) does the same.
        """
        for authenticator in authenticators:
            supported = authenticator.supports(request)
            if supported is False:
                log_debug(
                    self._logger,
                    'Authenticator "{authenticator}" no longer supports the request.',
                    {
                        "firewall": self._firewall_name,
                        "authenticator": authenticator_name(authenticator),
                    },
                )
                continue
            outcome = await self.execute_authenticator(
                authenticator, request, state, lazy=supported is None
            )
            if outcome is _ABSTAINED or outcome is None:
                continue
            response = cast("ResponseInterface", outcome)
            log_debug(
                self._logger,
                'Authenticator "{authenticator}" set the response.',
                {
                    "firewall": self._firewall_name,
                    "authenticator": authenticator_name(authenticator),
                },
            )
            return response
        return None

    async def execute_authenticator(
        self,
        authenticator: AuthenticatorInterface,
        request: ServerRequestInterface,
        state: SecurityState,
        *,
        lazy: bool,
    ) -> ResponseInterface | object | None:
        """Carry one authenticator through the sequence, or abstain when it does not apply."""
        passport: Passport | None = None
        # Read before the run stores anything, so the login-success event can
        # tell a listener what the storage held before this login replaced it.
        previous_token = self._token_storage.get_token()
        try:
            passport = await authenticator.authenticate(request)
            _ = await self._event_dispatcher.dispatch(
                CheckPassportEvent(authenticator, passport, request)
            )
            self._ensure_resolved(passport)
            _ = await passport.get_user()
            token = await authenticator.create_token(passport, self._firewall_name)
            token = (
                await self._event_dispatcher.dispatch(
                    AuthenticationTokenCreatedEvent(token, passport)
                )
            ).get_authenticated_token()
            _ = await self._event_dispatcher.dispatch(AuthenticationSuccessEvent(token))
            log_info(
                self._logger,
                "Authenticator successful!",
                {
                    "firewall": self._firewall_name,
                    "authenticator": authenticator_name(authenticator),
                },
            )
        except BadCredentialsError as error:
            if lazy and passport is None:
                return _ABSTAINED
            return await self.handle_authentication_failure(
                error, request, authenticator, passport, state
            )
        except AuthenticationError as error:
            return await self.handle_authentication_failure(
                error, request, authenticator, passport, state
            )
        response = await self.handle_authentication_success(
            token, passport, request, authenticator, previous_token
        )
        if response is not None:
            return response
        log_debug(
            self._logger,
            "Authenticator set no success response: request continues.",
            {
                "firewall": self._firewall_name,
                "authenticator": authenticator_name(authenticator),
            },
        )
        return None

    @override
    async def authenticate_user(
        self,
        user: UserInterface,
        authenticator: AuthenticatorInterface,
        request: ServerRequestInterface,
        badges: Sequence[BadgeInterface] = (),
        attributes: Mapping[str, object] | None = None,
    ) -> ResponseInterface | None:
        """Log ``user`` in through ``authenticator``, skipping every check.

        The caller vouches for the user, so there is nothing to verify: no
        passport check, no badge validation, no post-authentication account
        check. A self-validating passport is built around the user — a loader
        that hands them back — carrying the extra ``badges`` and
        ``attributes`` as given, the authenticator turns it into a token, and
        the login finishes exactly as a request-driven one does: the token is
        announced, stored, the success handler runs and the login-success
        event carries what the storage held before.
        """

        def _handed_back(*arguments: object) -> UserInterface:
            # The badge calls its loader with the identifier, and with the
            # attributes when it takes them; the user is already loaded, so
            # every spelling of the call hands the same one back.
            del arguments
            return user

        passport = SelfValidatingPassport(
            UserBadge(user.get_user_identifier(), user_loader=_handed_back),
            badges,
        )
        for name, value in (attributes or {}).items():
            passport.set_attribute(name, value)
        _ = await passport.get_user()
        token = await authenticator.create_token(passport, self._firewall_name)
        token = (
            await self._event_dispatcher.dispatch(AuthenticationTokenCreatedEvent(token, passport))
        ).get_authenticated_token()
        return await self.handle_authentication_success(
            token, passport, request, authenticator, self._token_storage.get_token()
        )

    async def handle_authentication_success(
        self,
        token: TokenInterface,
        passport: Passport,
        request: ServerRequestInterface,
        authenticator: AuthenticatorInterface,
        previous_token: TokenInterface | None,
    ) -> ResponseInterface | None:
        """Store the token, run the success handler, then announce the login.

        An authenticator that reports itself interactive — one a user actively
        logs in through, as opposed to a token re-establishing one — announces
        the login between the success handler and the login-success event,
        under the name
        :attr:`~xtr_security_http.security_events.SecurityEvents.INTERACTIVE_LOGIN`.
        """
        return await self._outcome.announce_login(
            token,
            passport,
            request,
            authenticator,
            previous_token,
        )

    async def handle_authentication_failure(
        self,
        error: AuthenticationError,
        request: ServerRequestInterface,
        authenticator: AuthenticatorInterface,
        passport: Passport | None,
        state: SecurityState,
    ) -> ResponseInterface | None:
        """Answer a failed authentication without ever raising.

        The error is masked to the configured level, the authenticator's
        failure handler runs first — its answer is what the event carries —
        and a listener may replace that answer through the event. A response
        from either is returned for the firewall to send; the lack of one
        means the request goes on anonymous, and the access decision is what
        turns that into a challenge — reading the masked error back off
        ``state``, where this step parked it, so the entry point's challenge
        can still name what went wrong.
        """
        return await self._outcome.answer_failure(
            error,
            request,
            authenticator,
            passport,
            state,
        )

    def _ensure_resolved(self, passport: Passport) -> None:
        """Raise when a badge is unresolved or a required badge is absent."""
        self._outcome.ensure_resolved(passport)
