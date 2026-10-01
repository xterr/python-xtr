"""The event announcing a completed, stored authentication."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response
    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from xtr_security_http.authenticator.authenticator_interface import AuthenticatorInterface
    from xtr_security_http.authenticator.passport.passport import Passport

__all__ = ["LoginSuccessEvent"]


@final
class LoginSuccessEvent(Event):
    """Announces that authentication succeeded, was stored, and produced a response.

    Dispatched after the token has been set on the storage and the
    authenticator's success handler has run. A listener reads the passport —
    to migrate an outdated password hash, to write an audit line — and may
    replace the response the success handler produced with one of its own.

    Not a frozen dataclass: a listener replacing the response mutates it.

    Attributes:
        authenticator: The authenticator that authenticated the request.
        firewall_name: The firewall the authentication ran under.
    """

    def __init__(  # noqa: PLR0913, PLR0917 -- an event carrying the login's full context
        self,
        authenticator: AuthenticatorInterface,
        passport: Passport,
        token: TokenInterface,
        request: Request,
        response: Response | None,
        firewall_name: str,
    ) -> None:
        """Record the authenticator, passport, token, request, response and firewall."""
        self._authenticator = authenticator
        self._passport = passport
        self._token = token
        self._request = request
        self._response = response
        self._firewall_name = firewall_name

    def get_authenticator(self) -> AuthenticatorInterface:
        """Return the authenticator that authenticated the request."""
        return self._authenticator

    def get_passport(self) -> Passport:
        """Return the passport authentication settled on."""
        return self._passport

    def get_authenticated_token(self) -> TokenInterface:
        """Return the token authentication settled on."""
        return self._token

    def get_request(self) -> Request:
        """Return the request that authenticated."""
        return self._request

    def get_response(self) -> Response | None:
        """Return the response the success handler produced, if any."""
        return self._response

    def set_response(self, response: Response | None) -> None:
        """Replace the response the login produced with ``response``."""
        self._response = response

    def get_firewall_name(self) -> str:
        """Return the firewall the authentication ran under."""
        return self._firewall_name
