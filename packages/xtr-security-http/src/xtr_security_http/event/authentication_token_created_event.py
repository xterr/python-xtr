"""The event that lets a listener replace the freshly created token."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from xtr_security_http.authenticator.passport.passport import Passport

__all__ = ["AuthenticationTokenCreatedEvent"]


@final
class AuthenticationTokenCreatedEvent(Event):
    """Announces that a token was created for a passport, before it is put to use.

    Dispatched right after an authenticator turned a resolved passport into a
    token. A listener may read the passport's badges and attributes and
    :meth:`set_authenticated_token` a token of its own — a richer one carrying
    extra claims, say — which then becomes the token authentication settles on.

    Not a frozen dataclass: replacing the token is the whole point, so the
    token it carries is mutable state.

    Attributes:
        passport: The passport the token was created from.
    """

    def __init__(self, token: TokenInterface, passport: Passport) -> None:
        """Record the created token and the passport it was made from."""
        self._token = token
        self._passport = passport

    def get_authenticated_token(self) -> TokenInterface:
        """Return the token as it currently stands, replacements included."""
        return self._token

    def set_authenticated_token(self, token: TokenInterface) -> None:
        """Replace the token authentication will settle on with ``token``."""
        self._token = token

    def get_passport(self) -> Passport:
        """Return the passport the token was created from."""
        return self._passport
