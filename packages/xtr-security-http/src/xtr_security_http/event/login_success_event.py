"""The event announcing a completed, stored authentication."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

from xtr_security_http.authenticator.debug.traceable_authenticator import TraceableAuthenticator

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface

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
        request: ServerRequestInterface,
        response: ResponseInterface | None,
        firewall_name: str,
        previous_token: TokenInterface | None = None,
    ) -> None:
        """Record the login's whole context, the token the storage held included.

        Args:
            authenticator: The authenticator that authenticated the request.
            passport: The passport authentication settled on.
            token: The token authentication settled on.
            request: The request that authenticated, as a message.
            response: The response the success handler produced, if any.
            firewall_name: The firewall the authentication ran under.
            previous_token: The token the storage held before this login set
                its own — what a listener migrating a session compares against.
        """
        self._authenticator = authenticator
        self._passport = passport
        self._token = token
        self._request = request
        self._response = response
        self._firewall_name = firewall_name
        self._previous_token = previous_token

    def get_authenticator(self) -> AuthenticatorInterface:
        """Return the authenticator that authenticated the request, unwrapped.

        A traceable wrapper is stored as given — the wiring decides what the
        manager runs — but a listener reading the event wants the real
        authenticator, so the wrapper is opened here rather than at
        construction.
        """
        if isinstance(self._authenticator, TraceableAuthenticator):
            return self._authenticator.get_authenticator()
        return self._authenticator

    def get_passport(self) -> Passport:
        """Return the passport authentication settled on."""
        return self._passport

    def get_authenticated_token(self) -> TokenInterface:
        """Return the token authentication settled on."""
        return self._token

    def get_previous_token(self) -> TokenInterface | None:
        """Return the token the storage held before this login, if any."""
        return self._previous_token

    def get_user(self) -> UserInterface:
        """Return the user the passport loaded, the login's whole point."""
        return self._passport.get_user_badge().get_loaded_user()

    def get_request(self) -> ServerRequestInterface:
        """Return the request that authenticated, as a message."""
        return self._request

    def get_response(self) -> ResponseInterface | None:
        """Return the response the success handler produced, if any."""
        return self._response

    def set_response(self, response: ResponseInterface | None) -> None:
        """Replace the response the login produced with ``response``."""
        self._response = response

    def get_firewall_name(self) -> str:
        """Return the firewall the authentication ran under."""
        return self._firewall_name
