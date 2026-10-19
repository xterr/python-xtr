"""The listener that records the methods a login proved, and keeps them across logins.

A successful login replaces the token, so the proofs the previous token carried
would be lost with it: a second factor proven at login has to survive a password
re-check hours later for a policy to be able to require both. The listener
records the methods an interactive login proved at the moment it succeeds, and
carries the previous token's proofs over while the user is the same.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_clock import SystemClock
from xtr_event_dispatcher import EventSubscriberInterface
from xtr_security_core.authentication.authentication_method import AuthenticationMethod
from xtr_security_core.authentication.token.remember_me_token import RememberMeToken

from xtr_security_http.authenticator.interactive_authenticator_interface import (
    InteractiveAuthenticatorInterface,
)
from xtr_security_http.authenticator.passport.badge.authentication_method_badge import (
    AuthenticationMethodBadge,
)
from xtr_security_http.event.login_success_event import LoginSuccessEvent

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_clock import ClockInterface
    from xtr_event_dispatcher import SubscribedEvents
    from xtr_security_core.authentication.token.token_interface import TokenInterface

__all__ = ["PRIORITY", "AuthenticationProofsListener"]

#: The priority the proofs are recorded at — above every other login-success
#: listener, so a listener that stops propagation cannot leave the token
#: without the record the authenticated-recently check is decided on.
PRIORITY: Final = 256


@final
class AuthenticationProofsListener(EventSubscriberInterface):
    """Records the methods an interactive login proved, and carries proofs across logins.

    An interactive login, other than a remember-me one, is recorded at the
    moment it succeeds: the methods its authentication method badge states are
    added to whatever the token already holds, the newer entry winning; with no
    badge, an unspecified method is recorded only when the token holds nothing
    yet. A remember-me login records nothing — presenting a cookie proves nothing
    about the credentials — and an authenticator that records its own proofs on
    the token keeps them, since only a gap is ever filled.

    A login whose previous token names the same user carries that token's proofs
    over, the token's own entries winning, so a second factor proven at login
    survives a later password re-check.
    """

    __slots__ = ("_clock",)

    def __init__(self, clock: ClockInterface | None = None) -> None:
        """Record the reader of the current instant, the proofs are stamped with.

        Args:
            clock: The reader of the current instant. Defaults to the system clock.
        """
        self._clock: ClockInterface = clock if clock is not None else SystemClock()

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Listen to a successful, stored login, ahead of the other login-success listeners."""
        return {LoginSuccessEvent: ("on_login_success", PRIORITY)}

    async def on_login_success(self, event: LoginSuccessEvent) -> None:
        """Record the login's proofs, then carry the previous token's over.

        The proofs are recorded on the authenticated token, and only then is
        the previous token consulted: the carry-over merges into what the
        login has just recorded, not the reverse.
        """
        token = event.get_authenticated_token()
        authenticator = event.get_authenticator()
        if (
            isinstance(authenticator, InteractiveAuthenticatorInterface)
            and authenticator.is_interactive()
            and not isinstance(token, RememberMeToken)
        ):
            self._record_proofs(event, token)

        previous_token = event.get_previous_token()
        if previous_token is None or (
            previous_token.get_user_identifier() != token.get_user_identifier()
        ):
            return
        previous_proofs = previous_token.get_authentication_proofs()
        if not previous_proofs:
            return
        token.set_authentication_proofs({**previous_proofs, **token.get_authentication_proofs()})

    def _record_proofs(self, event: LoginSuccessEvent, token: TokenInterface) -> None:
        """Record the methods the passport states, or an unspecified one when none is stated."""
        now = int(self._clock.now().timestamp())
        badge = event.get_passport().get_badge(AuthenticationMethodBadge)
        if isinstance(badge, AuthenticationMethodBadge):
            stated = dict.fromkeys(badge.get_methods(), now)
            # A stated method is a new proof even on a token that already holds it:
            # the second step of a 2FA flow authenticates the first step's token again.
            token.set_authentication_proofs({**token.get_authentication_proofs(), **stated})
        elif not token.get_authentication_proofs():
            token.set_authentication_proofs({AuthenticationMethod.UNSPECIFIED: now})
