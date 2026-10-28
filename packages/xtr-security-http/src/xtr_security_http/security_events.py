"""The names the security events of the HTTP edge run under.

Most events here carry no name of their own: a listener subscribes to the
event class and the dispatcher derives the name from it. The two that do
carry one — a user actively logging in, a user switching to another — are
announced under that name instead, and this module is where the name
lives, so the code that raises them, the listeners that answer them and
the docs that describe them share one spelling from the day the events
land.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from xtr_event_dispatcher_contracts import event_name_of

from .event.authentication_token_created_event import AuthenticationTokenCreatedEvent
from .event.check_passport_event import CheckPassportEvent
from .event.check_refreshed_user_event import CheckRefreshedUserEvent
from .event.interactive_login_event import InteractiveLoginEvent
from .event.login_failure_event import LoginFailureEvent
from .event.login_success_event import LoginSuccessEvent
from .event.logout_event import LogoutEvent
from .event.oidc_authorization_request_event import OidcAuthorizationRequestEvent
from .event.switch_user_event import SwitchUserEvent
from .event.token_deauthenticated_event import TokenDeauthenticatedEvent

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher_contracts import Event

__all__ = ["SecurityEvents"]


@final
class SecurityEvents:
    """The names of the security events, and the classes they belong to.

    The named events — an interactive login, a user switch — are the ones
    an application listens for across the whole flow rather than at one
    authenticator, which is why they carry a name of their own instead of
    running under their class's qualified name.

    :attr:`ALIASES` is the lookup between the two spellings: every event
    class this package raises today, mapped to the name it runs under. The
    class-keyed ones map to the qualified name the dispatcher derives; the
    named ones — the interactive login, the user switch — map to the names
    they carry.
    """

    INTERACTIVE_LOGIN: Final[str] = "security.interactive_login"
    """Announced after a user actively authenticated — a form submitted, a
    login link followed — as opposed to a session or a bearer token
    re-establishing the same user passively."""

    SWITCH_USER: Final[str] = "security.switch_user"
    """Announced before a user switches to another by impersonating them,
    and before an impersonation is left."""

    ALIASES: Final[Mapping[type[Event], str]] = {
        AuthenticationTokenCreatedEvent: event_name_of(AuthenticationTokenCreatedEvent),
        CheckPassportEvent: event_name_of(CheckPassportEvent),
        CheckRefreshedUserEvent: event_name_of(CheckRefreshedUserEvent),
        InteractiveLoginEvent: INTERACTIVE_LOGIN,
        LoginFailureEvent: event_name_of(LoginFailureEvent),
        LoginSuccessEvent: event_name_of(LoginSuccessEvent),
        LogoutEvent: event_name_of(LogoutEvent),
        OidcAuthorizationRequestEvent: event_name_of(OidcAuthorizationRequestEvent),
        SwitchUserEvent: SWITCH_USER,
        TokenDeauthenticatedEvent: event_name_of(TokenDeauthenticatedEvent),
    }
    """Every event class this package raises today, mapped to the name it is
    dispatched under."""
