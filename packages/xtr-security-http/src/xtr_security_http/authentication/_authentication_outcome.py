"""How one authentication attempt ends: resolved, announced, or answered.

The manager runs the passes; answering how an attempt ends is a concern of
its own — the badge resolution that fails an unresolved passport, the
token-and-events sequence that announces a login, the masked answer that
closes a failure without ever raising — and every answer is built from the
same wiring, so the three live together here, handed that wiring once.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from xtr_security_core.exception import BadCredentialsError

from xtr_security_http.authentication._sensitive import mask
from xtr_security_http.authenticator.interactive_authenticator_interface import (
    InteractiveAuthenticatorInterface,
)
from xtr_security_http.event.interactive_login_event import InteractiveLoginEvent
from xtr_security_http.event.login_failure_event import LoginFailureEvent
from xtr_security_http.event.login_success_event import LoginSuccessEvent
from xtr_security_http.security_events import SecurityEvents
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from ._manager_reporting import authenticator_name, log_debug, log_info

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_security_core.authentication.token.storage.token_storage_interface import (
        TokenStorageInterface,
    )
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.exception import AuthenticationError

    from xtr_security_http._security_state import SecurityState
    from xtr_security_http.authentication.expose_security_level import ExposeSecurityLevel
    from xtr_security_http.authenticator.authenticator_interface import AuthenticatorInterface
    from xtr_security_http.authenticator.passport.badge.badge_interface import BadgeInterface
    from xtr_security_http.authenticator.passport.passport import Passport

__all__ = [
    "AuthenticationOutcome",
    "ManagerWiring",
]


@final
@dataclass(frozen=True, slots=True)
class ManagerWiring:
    """The collaborators every answer of an authentication is built from."""

    storage: TokenStorageInterface
    dispatcher: EventDispatcherInterface
    firewall_name: str
    logger: LoggerInterface | None
    expose_security_errors: ExposeSecurityLevel
    required_badges: tuple[type[BadgeInterface], ...]


@final
class AuthenticationOutcome:
    """Answers how one authentication attempt ends.

    The three answers the manager's passes hand over to: the badge check
    that fails an unresolved passport, the token-and-events sequence that
    announces a successful login, and the masked, never-raising answer that
    closes a failure.
    """

    __slots__ = ("_wiring",)

    def __init__(self, wiring: ManagerWiring) -> None:
        """Record the wiring every answer is built from."""
        self._wiring = wiring

    def ensure_resolved(self, passport: Passport) -> None:
        """Raise when a badge is unresolved or a required badge is absent.

        An unresolved badge fails fast, naming the first one the passport
        carries; the required ones are checked as a group, so one error names
        every badge the firewall asked for and the passport lacks.

        Raises:
            BadCredentialsError: When a badge is unresolved, or a required
                one is absent.
        """
        for badge in passport.get_badges().values():
            if not badge.is_resolved():
                raise BadCredentialsError(
                    f"The badge {type(badge).__name__} was not resolved by the passport check.",
                )
        missing = [badge for badge in self._wiring.required_badges if not passport.has_badge(badge)]
        if missing:
            raise BadCredentialsError(
                "The passport is missing the required badges: "
                + ", ".join(badge.__name__ for badge in missing)
                + ".",
            )

    async def announce_login(
        self,
        token: TokenInterface,
        passport: Passport,
        request: ServerRequestInterface,
        authenticator: AuthenticatorInterface,
        previous_token: TokenInterface | None,
    ) -> ResponseInterface | None:
        """Store the token, run the success handler, then announce the login.

        An authenticator that reports itself interactive — one a user
        actively logs in through, as opposed to a token re-establishing one —
        announces the login between the success handler and the login-success
        event, under the name
        :attr:`~xtr_security_http.security_events.SecurityEvents.INTERACTIVE_LOGIN`.
        """
        self._wiring.storage.set_token(token)
        response = await authenticator.on_authentication_success(
            request,
            token,
            self._wiring.firewall_name,
        )
        if (
            isinstance(authenticator, InteractiveAuthenticatorInterface)
            and authenticator.is_interactive()
        ):
            _ = await self._wiring.dispatcher.dispatch(
                InteractiveLoginEvent(request, token),
                SecurityEvents.INTERACTIVE_LOGIN,
            )
        event = LoginSuccessEvent(
            authenticator,
            passport,
            token,
            request,
            response,
            self._wiring.firewall_name,
            previous_token,
        )
        _ = await self._wiring.dispatcher.dispatch(event)
        return event.get_response()

    async def answer_failure(
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
        masked = mask(error, self._wiring.expose_security_errors)
        state.attributes[SecurityRequestAttributes.AUTHENTICATION_ERROR] = masked
        log_info(
            self._wiring.logger,
            "Authentication failed.",
            {"firewall": self._wiring.firewall_name, "error": type(error).__name__},
        )
        response = await authenticator.on_authentication_failure(request, masked)
        if response is not None:
            log_debug(
                self._wiring.logger,
                'Authenticator "{authenticator}" set the failure response.',
                {
                    "firewall": self._wiring.firewall_name,
                    "authenticator": authenticator_name(authenticator),
                },
            )
        event = LoginFailureEvent(
            masked,
            authenticator,
            request,
            response,
            self._wiring.firewall_name,
            passport,
        )
        _ = await self._wiring.dispatcher.dispatch(event)
        return event.get_response()
