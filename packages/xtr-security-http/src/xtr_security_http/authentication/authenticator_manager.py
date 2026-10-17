"""Drives a firewall's authenticators over one request, in the fixed order."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_security_core.event.authentication_success_event import AuthenticationSuccessEvent
from xtr_security_core.exception import (
    AuthenticationError,
    BadCredentialsError,
    InvalidArgumentError,
)

from xtr_security_http.authentication._sensitive import mask
from xtr_security_http.authentication.expose_security_level import ExposeSecurityLevel
from xtr_security_http.authenticator.authenticator_interface import AuthenticatorInterface
from xtr_security_http.event.authentication_token_created_event import (
    AuthenticationTokenCreatedEvent,
)
from xtr_security_http.event.check_passport_event import CheckPassportEvent
from xtr_security_http.event.login_failure_event import LoginFailureEvent
from xtr_security_http.event.login_success_event import LoginSuccessEvent
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from .authenticator_manager_interface import AuthenticatorManagerInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_logging_contracts.context import Context
    from xtr_security_core.authentication.token.storage.token_storage_interface import (
        TokenStorageInterface,
    )
    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from xtr_security_http._security_state import SecurityState
    from xtr_security_http.authenticator.passport.badge.badge_interface import BadgeInterface
    from xtr_security_http.authenticator.passport.passport import Passport

__all__ = ["AuthenticatorManager"]

#: Returned when a lazy authenticator did not apply — no credential was presented.
_ABSTAINED: object = object()


@final
class AuthenticatorManager(AuthenticatorManagerInterface):
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
        lazy = True
        skipped: list[AuthenticatorInterface] = []
        authenticators: list[AuthenticatorInterface] = []
        for authenticator in self._authenticators:
            # The sequence is typed, but nothing stops a caller from wiring a
            # duck-typed impostor in; the pass refuses one here, where the
            # mistake is about to cost a request.
            if not isinstance(  # pyright: ignore[reportUnnecessaryIsInstance]
                authenticator,
                AuthenticatorInterface,
            ):
                raise InvalidArgumentError(
                    f'The authenticator "{type(authenticator).__name__}" does not implement '
                    f"AuthenticatorInterface.",
                )
            supported = authenticator.supports(request)
            if supported is False:
                self._debug(
                    'Authenticator "{authenticator}" does not support the request.',
                    {
                        "firewall": self._firewall_name,
                        "authenticator": type(authenticator).__name__,
                    },
                )
                skipped.append(authenticator)
            else:
                self._debug(
                    'Authenticator "{authenticator}" supports the request.',
                    {
                        "firewall": self._firewall_name,
                        "authenticator": type(authenticator).__name__,
                    },
                )
                authenticators.append(authenticator)
                lazy = supported is None and lazy
        state.attributes[SecurityRequestAttributes.SKIPPED_AUTHENTICATORS] = tuple(skipped)
        state.attributes[SecurityRequestAttributes.AUTHENTICATORS] = tuple(authenticators)
        if not authenticators:
            return False
        self._debug(
            'Authenticators "{authenticators}" support the request.',
            {
                "firewall": self._firewall_name,
                "authenticators": [
                    type(authenticator).__name__ for authenticator in authenticators
                ],
            },
        )
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
        tried and, failing that, the request stays anonymous. Any other failure
        from it, and every failure from an eager authenticator, is a real
        authentication failure the firewall turns into a challenge.
        """
        parked = state.attributes.pop(SecurityRequestAttributes.AUTHENTICATORS, None)
        _ = state.attributes.pop(SecurityRequestAttributes.SKIPPED_AUTHENTICATORS, None)
        if not parked:
            return None
        return await self.execute_authenticators(
            cast("tuple[AuthenticatorInterface, ...]", parked),
            request,
        )

    async def execute_authenticators(
        self,
        authenticators: Sequence[AuthenticatorInterface],
        request: ServerRequestInterface,
    ) -> ResponseInterface | None:
        """Run the handed-off authenticators in order, re-checking each first.

        The re-check is per authenticator — never the full supports pass
        again — because what the request carries may have changed between
        the pass and now. A re-check that turned ``False`` skips its
        authenticator with a note; the first authenticator that applies and
        settles the request ends the run, whether it answered with a
        response or left the request to go on.
        """
        for authenticator in authenticators:
            supported = authenticator.supports(request)
            if supported is False:
                self._debug(
                    'Authenticator "{authenticator}" no longer supports the request.',
                    {
                        "firewall": self._firewall_name,
                        "authenticator": type(authenticator).__name__,
                    },
                )
                continue
            outcome = await self.execute_authenticator(
                authenticator, request, lazy=supported is None
            )
            if outcome is not _ABSTAINED:
                response = cast("ResponseInterface | None", outcome)
                if response is not None:
                    self._debug(
                        'Authenticator "{authenticator}" set the response.',
                        {
                            "firewall": self._firewall_name,
                            "authenticator": type(authenticator).__name__,
                        },
                    )
                return response
        return None

    async def execute_authenticator(
        self,
        authenticator: AuthenticatorInterface,
        request: ServerRequestInterface,
        *,
        lazy: bool,
    ) -> ResponseInterface | object | None:
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
        """Raise when a badge is unresolved or a required badge is absent.

        An unresolved badge fails fast, naming the first one the passport
        check left open. The required badges are gathered first and named
        together, so a passport missing several reports them all in one
        failure instead of one failure per badge.
        """
        passport.check_if_completely_resolved()
        missing = [badge for badge in self._required_badges if not passport.has_badge(badge)]
        if missing:
            raise BadCredentialsError(
                "The passport is missing the required badges: "
                + ", ".join(badge.__name__ for badge in missing)
                + ".",
            )

    def _debug(self, message: str, context: Context) -> None:
        """Log ``message`` at debug level, when a logger was given."""
        if self._logger is not None:
            self._logger.debug(message, context)

    async def _token_created(self, token: TokenInterface, passport: Passport) -> TokenInterface:
        """Announce the created token and return whichever token a listener settled on."""
        event = AuthenticationTokenCreatedEvent(token, passport)
        _ = await self._event_dispatcher.dispatch(event)
        return event.get_authenticated_token()

    async def _on_success(
        self,
        authenticator: AuthenticatorInterface,
        request: ServerRequestInterface,
        passport: Passport,
        token: TokenInterface,
    ) -> ResponseInterface | None:
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
        request: ServerRequestInterface,
        passport: Passport | None,
        error: AuthenticationError,
    ) -> ResponseInterface | None:
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
