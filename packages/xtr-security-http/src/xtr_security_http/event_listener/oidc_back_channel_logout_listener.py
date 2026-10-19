"""Deauthenticating a token whose provider session a back-channel logout ended."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_http.exception.oidc_session_ended_error import OidcSessionEndedError

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from xtr_security_http.event.check_refreshed_user_event import CheckRefreshedUserEvent
    from xtr_security_http.oidc.oidc_ended_sessions import OidcEndedSessions

__all__ = ["OidcBackChannelLogoutListener"]

_SID_ATTRIBUTE: str = "oidc_sid"
"""Where the firewall keeps the session the provider names, when it does."""


@final
class OidcBackChannelLogoutListener:
    """Deauthenticates a token whose provider session a back-channel logout ended.

    The login stops working on the next request the browser makes. The
    logout token arrives outside of any request of the end-user, so its
    arrival can only be written down; this is where it is acted on, the
    token being the one thing saying which provider session the login
    belongs to.

    It is a plain callable rather than a subscriber, registered by the
    wiring on the dispatcher the refreshed-user check is announced on: the
    check runs on every request of a stateful firewall, and this listener
    is the application's to place — one per firewall, over the ended
    sessions that firewall's provider pushed.

    Running on every firewall does not make it refuse the logins of another:
    a token names the firewall it was minted on, and only the listener of
    that firewall acts on it. Two providers minting the same opaque ``sid``
    for two firewalls would otherwise have one end the logins of the other.

    It costs one cache lookup on each request carrying an ``oidc_sid``
    attribute, and nothing on the others.

    Deauthenticating is where it stops, which is what a password change
    does too: an application wanting its session invalidated as well reads
    the session-ended error off the deauthentication event.
    """

    __slots__ = ("_ended_sessions", "_firewall_name")

    def __init__(
        self,
        ended_sessions: OidcEndedSessions,
        firewall_name: str,
    ) -> None:
        """Record the ended sessions this firewall's provider pushed.

        Args:
            ended_sessions: The ended sessions of the provider this
                firewall logs in through.
            firewall_name: The firewall whose provider sessions
                ``ended_sessions`` records.
        """
        self._ended_sessions = ended_sessions
        self._firewall_name = firewall_name

    async def __call__(self, event: CheckRefreshedUserEvent) -> None:
        """Refuse the token of a session a back-channel logout ended.

        Two kinds of token are left untouched, and cost no lookup.

        One minted on another firewall, whose ended sessions another
        listener records, and one naming no provider session at all, which
        a login made through another authenticator or before this firewall
        asked for the ``sid`` claim cannot be matched by.
        """
        token = event.get_token()

        # A token of a kind carrying the name of the firewall that
        # authenticated it is asked for it, and one of another kind
        # resolves nothing.
        firewall_name = getattr(token, "get_firewall_name", None)
        if firewall_name is None or firewall_name() != self._firewall_name:
            return

        sid = _attribute(token, _SID_ATTRIBUTE)

        if not isinstance(sid, str) or not sid:
            return

        if await self._ended_sessions.has(sid):
            event.set_user_changed(True, OidcSessionEndedError())  # noqa: FBT003 -- the upstream call shape: the verdict is the reason's own, not a flag


def _attribute(token: TokenInterface, name: str) -> object:
    """Return the attribute ``name`` a token carries, or ``None`` without it."""
    return token.get_attribute(name) if token.has_attribute(name) else None
