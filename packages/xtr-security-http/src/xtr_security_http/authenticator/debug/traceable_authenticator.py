"""An authenticator that records what the wrapped one did, for the tooling."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_clock import SystemClock

from xtr_security_http.authenticator.authenticator_interface import AuthenticatorInterface
from xtr_security_http.authenticator.interactive_authenticator_interface import (
    InteractiveAuthenticatorInterface,
)
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from .unsupported_reasons import UnsupportedReasons

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_clock import ClockInterface
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.exception import AuthenticationError

    from xtr_security_http.authenticator.passport.passport import Passport

__all__ = ["TraceableAuthenticator"]


@final
class TraceableAuthenticator(AuthenticatorInterface, InteractiveAuthenticatorInterface):
    """Wraps an authenticator and records each answer it gives.

    The wiring swaps an authenticator for one of these when the tooling needs
    to explain a firewall's decision: which authenticator supported the
    request, what passport it built, how long that took, whether it
    authenticated and what it failed with. The wrapper changes nothing about
    the flow — every call is passed through as it came — it only listens.

    The wrapped authenticator is stored as given, never unwrapped here: the
    event getters and the manager's logs open the wrapper where they want the
    real authenticator's name, so :meth:`get_authenticator` is the only door.

    The duration is read off the injected clock as the wall-clock delta, in
    float seconds. The clock rule mandates the injectable clock, so tests can
    freeze it; a monotonic reading would survive NTP steps, but the duration
    of a debug trace tolerates the wall clock, and the rule keeps one time
    source for the package.
    """

    __slots__ = (
        "_authenticated",
        "_authenticator",
        "_clock",
        "_duration",
        "_exception",
        "_passport",
        "_supports",
        "_unsupported_reasons",
    )

    def __init__(
        self,
        authenticator: AuthenticatorInterface,
        clock: ClockInterface | None = None,
    ) -> None:
        """Wrap ``authenticator`` with every record empty, timing it on ``clock``.

        Args:
            authenticator: The authenticator to wrap and record.
            clock: The clock reading the authentication's start and end; the
                system clock when ``None``.
        """
        self._authenticator = authenticator
        self._clock = clock if clock is not None else SystemClock()
        self._supports: bool | None = False
        self._unsupported_reasons: tuple[str, ...] = ()
        self._passport: Passport | None = None
        self._duration: float | None = None
        self._authenticated: bool | None = None
        self._exception: AuthenticationError | None = None

    @override
    def supports(self, request: ServerRequestInterface) -> bool | None:
        """Record the wrapped answer, collecting any reasons for a negative one.

        A fresh :class:`UnsupportedReasons` rides the request — under
        :attr:`~xtr_security_http.security_request_attributes.SecurityRequestAttributes.UNSUPPORTED_REASONS`
        — for exactly this call, so the wrapped authenticator can explain
        itself while it answers; the attribute is gone again by the time the
        caller sees the answer.
        """
        reasons = UnsupportedReasons()
        self._supports = self._authenticator.supports(
            request.with_attribute(SecurityRequestAttributes.UNSUPPORTED_REASONS, reasons),
        )
        self._unsupported_reasons = reasons.all()
        return self._supports

    @override
    async def authenticate(self, request: ServerRequestInterface) -> Passport:
        """Record the passport the wrapped authenticator built, and how long."""
        started = self._clock.now().timestamp()
        try:
            self._passport = await self._authenticator.authenticate(request)
        finally:
            self._duration = self._clock.now().timestamp() - started
        return self._passport

    @override
    async def create_token(self, passport: Passport, firewall_name: str) -> TokenInterface:
        """Pass through, so the wrapped authenticator builds the token."""
        return await self._authenticator.create_token(passport, firewall_name)

    @override
    async def on_authentication_success(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
        firewall_name: str,
    ) -> ResponseInterface | None:
        """Record that the wrapped authenticator authenticated, then pass through."""
        self._authenticated = True
        return await self._authenticator.on_authentication_success(request, token, firewall_name)

    @override
    async def on_authentication_failure(
        self,
        request: ServerRequestInterface,
        error: AuthenticationError,
    ) -> ResponseInterface | None:
        """Record the failure the wrapped authenticator answered, then pass through."""
        self._authenticated = False
        self._exception = error
        return await self._authenticator.on_authentication_failure(request, error)

    def get_authenticator(self) -> AuthenticatorInterface:
        """Return the wrapped authenticator, the one the wiring really runs."""
        return self._authenticator

    @override
    def is_interactive(self) -> bool:
        """Answer for the wrapped authenticator, so tracing changes no announcement.

        A wrapped form login is a form login still: the manager asks here,
        and the interactive-login announcement fires exactly as it would
        without the wrapper — which is the wrapper's whole contract, that
        every call is passed through as it came.
        """
        return (
            isinstance(
                self._authenticator,
                InteractiveAuthenticatorInterface,
            )
            and self._authenticator.is_interactive()
        )

    def get_info(self) -> Mapping[str, object]:
        """Return everything recorded about the wrapped authenticator so far."""
        return {
            "supports": self._supports,
            "unsupported_reasons": self._unsupported_reasons,
            "passport": self._passport,
            "duration": self._duration,
            "authenticated": self._authenticated,
            "exception": self._exception,
        }
