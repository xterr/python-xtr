"""The event announcing a failed authentication."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response
    from xtr_security_core.exception import AuthenticationError

    from xtr_security_http.authenticator.authenticator_interface import AuthenticatorInterface
    from xtr_security_http.authenticator.passport.passport import Passport

__all__ = ["LoginFailureEvent"]


@final
class LoginFailureEvent(Event):
    """Announces that authentication failed, and lets a listener answer it.

    Dispatched when an authenticator raised — after the error was masked, if
    the firewall hides sensitive failures — before the authenticator's failure
    handler runs. A listener reads the error and the passport that got as far
    as it did, and may :meth:`set_response` to answer the failure itself,
    short-circuiting the failure handler.

    Not a frozen dataclass: setting the response mutates it.

    Attributes:
        firewall_name: The firewall the authentication ran under.
    """

    def __init__(  # noqa: PLR0913, PLR0917 -- an event carrying the failure's full context
        self,
        exception: AuthenticationError,
        authenticator: AuthenticatorInterface,
        request: Request,
        passport: Passport | None,
        firewall_name: str,
        response: Response | None = None,
    ) -> None:
        """Record the error, authenticator, request, passport, firewall and response."""
        self._exception = exception
        self._authenticator = authenticator
        self._request = request
        self._passport = passport
        self._firewall_name = firewall_name
        self._response = response

    def get_exception(self) -> AuthenticationError:
        """Return the error authentication failed with."""
        return self._exception

    def get_authenticator(self) -> AuthenticatorInterface:
        """Return the authenticator that failed to authenticate the request."""
        return self._authenticator

    def get_request(self) -> Request:
        """Return the request that failed to authenticate."""
        return self._request

    def get_passport(self) -> Passport | None:
        """Return the passport, if one was produced before the failure."""
        return self._passport

    def get_firewall_name(self) -> str:
        """Return the firewall the authentication ran under."""
        return self._firewall_name

    def get_response(self) -> Response | None:
        """Return the response a listener set to answer the failure, if any."""
        return self._response

    def set_response(self, response: Response | None) -> None:
        """Answer the failure with ``response`` instead of the failure handler."""
        self._response = response
