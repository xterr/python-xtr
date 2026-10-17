"""The event announcing a failed authentication."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

from xtr_security_http.authenticator.debug.traceable_authenticator import TraceableAuthenticator

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.exception import AuthenticationError

    from xtr_security_http.authenticator.authenticator_interface import AuthenticatorInterface
    from xtr_security_http.authenticator.passport.passport import Passport

__all__ = ["LoginFailureEvent"]


@final
class LoginFailureEvent(Event):
    """Announces that authentication failed, and lets a listener answer it.

    Dispatched when an authenticator raised — after the error was masked, if
    the firewall hides sensitive failures, and after the authenticator's
    failure handler ran. A listener reads the error, the passport that got as
    far as it did and the response the handler produced, and may
    :meth:`set_response` to answer the failure itself.

    Not a frozen dataclass: setting the response mutates it.

    Attributes:
        firewall_name: The firewall the authentication ran under.
    """

    def __init__(  # noqa: PLR0913, PLR0917 -- an event carrying the failure's full context
        self,
        exception: AuthenticationError,
        authenticator: AuthenticatorInterface,
        request: ServerRequestInterface,
        response: ResponseInterface | None,
        firewall_name: str,
        passport: Passport | None = None,
    ) -> None:
        """Record the failure's whole context, the handler's answer included.

        Args:
            exception: The error authentication failed with, masked already
                when the firewall hides sensitive failures.
            authenticator: The authenticator that failed to authenticate.
            request: The request that failed to authenticate, as a message.
            firewall_name: The firewall the authentication ran under.
            passport: The passport, if one was produced before the failure.
            response: The response the failure handler produced, if any —
                a listener may replace it.
        """
        self._exception = exception
        self._authenticator = authenticator
        self._request = request
        self._firewall_name = firewall_name
        self._passport = passport
        self._response = response

    def get_exception(self) -> AuthenticationError:
        """Return the error authentication failed with."""
        return self._exception

    def get_authenticator(self) -> AuthenticatorInterface:
        """Return the authenticator that failed, unwrapped from any traceable.

        A traceable wrapper is stored as given — the wiring decides what the
        manager runs — but a listener reading the event wants the real
        authenticator, so the wrapper is opened here rather than at
        construction.
        """
        if isinstance(self._authenticator, TraceableAuthenticator):
            return self._authenticator.get_authenticator()
        return self._authenticator

    def get_request(self) -> ServerRequestInterface:
        """Return the request that failed to authenticate, as a message."""
        return self._request

    def get_passport(self) -> Passport | None:
        """Return the passport, if one was produced before the failure."""
        return self._passport

    def get_firewall_name(self) -> str:
        """Return the firewall the authentication ran under."""
        return self._firewall_name

    def get_response(self) -> ResponseInterface | None:
        """Return the response a listener set to answer the failure, if any."""
        return self._response

    def set_response(self, response: ResponseInterface | None) -> None:
        """Answer the failure with ``response`` instead of the failure handler."""
        self._response = response
