"""The listener that hands a successful login to the firewall's session strategy."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface
from xtr_http_foundation import Session

from xtr_security_http._security_state import security_state_of
from xtr_security_http.event.login_success_event import LoginSuccessEvent
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents
    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_http.session.session_authentication_strategy_interface import (
        SessionAuthenticationStrategyInterface,
    )

__all__ = ["SessionStrategyListener"]


@final
class SessionStrategyListener(EventSubscriberInterface):
    """Rotates the session after a successful login, the way the firewall configured.

    A subscriber on the login-success event, on the firewall's own
    dispatcher: the login has been stored and the success handler has
    answered, and the request that authenticated is still the one being
    answered — the moment the session's ID is rotated, so the response
    re-issues the rotated ID and the token is written back under it.

    The listener skips a login that has no session to move: the request
    whose security state carries no session — a stateless firewall, or a
    login outside a stateful chain — has nothing the strategy could
    rotate. It skips a re-authentication of the same account, too: the
    previous token names the same, non-empty user identifier and is of
    the same class as the new one, so the session already answers for
    this account and rotating it would log out the very login it
    celebrates.

    Register it on every *stateful* firewall's dispatcher, with the
    strategy the firewall configured.
    """

    __slots__ = ("_session_authentication_strategy",)

    def __init__(
        self,
        session_authentication_strategy: SessionAuthenticationStrategyInterface,
    ) -> None:
        """Record the strategy this firewall's logins hand the session to.

        Args:
            session_authentication_strategy: The strategy the firewall
                configured — what one of its logins does to the session
                the request reattached.
        """
        self._session_authentication_strategy = session_authentication_strategy

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Listen to a successful, stored login."""
        return {LoginSuccessEvent: "on_login_success"}

    async def on_login_success(self, event: LoginSuccessEvent) -> None:
        """Hand the login's request and token to the strategy, unless it is a re-login.

        The strategy is reached with the event's own request and
        authenticated token, at the default priority a subscriber carries
        — beside the other listeners of the login-success event, in the
        order they were added.
        """
        request = event.get_request()
        token = event.get_authenticated_token()
        if not self._has_session(request):
            return
        previous_token = event.get_previous_token()
        if previous_token is not None:
            identifier = token.get_user_identifier()
            if (
                identifier != ""
                and identifier == previous_token.get_user_identifier()
                and type(token) is type(previous_token)
            ):
                return
        await self._session_authentication_strategy.on_authentication(request, token)

    def _has_session(self, request: ServerRequestInterface) -> bool:
        """Tell whether the request's security state carries a session.

        The context listener's park is how this stack says a request has a
        session: it is the one object the request's halves share, and the
        one the strategy rotates. A request whose state holds none ran no
        stateful machinery, so there is no session for the strategy to
        move.
        """
        bag = request.get_attribute(SecurityRequestAttributes.STATE_BAG)
        if not isinstance(bag, MutableMapping):
            return False
        session = security_state_of(cast("MutableMapping[str, object]", bag)).attributes.get(
            SecurityRequestAttributes.SESSION
        )
        return isinstance(session, Session)
