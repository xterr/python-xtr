"""Makes the main dispatcher's security listeners listen on every firewall's dispatcher too."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast, final

from xtr_event_dispatcher import EventDispatcherInterface
from xtr_security_core.event.authentication_success_event import AuthenticationSuccessEvent
from xtr_security_http.event.authentication_token_created_event import (
    AuthenticationTokenCreatedEvent,
)
from xtr_security_http.event.check_passport_event import CheckPassportEvent
from xtr_security_http.event.login_failure_event import LoginFailureEvent
from xtr_security_http.event.login_success_event import LoginSuccessEvent

from .firewall_dispatcher_name import firewall_dispatcher_name
from .security_config import SecurityConfig

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder
    from xtr_event_dispatcher.bundle import ListenerMap

__all__ = ["RegisterGlobalSecurityEventListenersPass"]

_BUBBLING_EVENTS: Final = (
    CheckPassportEvent,
    AuthenticationTokenCreatedEvent,
    AuthenticationSuccessEvent,
    LoginSuccessEvent,
    LoginFailureEvent,
)
"""The events a firewall dispatches on its own dispatcher that the main one's listeners hear."""


@final
class RegisterGlobalSecurityEventListenersPass:
    """Gives every firewall's dispatcher the main dispatcher's listeners of the security events.

    A firewall dispatches its security events on a dispatcher of its own, so
    that a listener can hear one firewall alone. One declared on the main
    dispatcher — an application's ``@as_event_listener`` on
    :class:`LoginSuccessEvent`, the credentials check every firewall shares —
    hears every firewall's: this pass adds it to each, by priority, after the
    firewall's own listeners of the same priority.

    The security bundle registers it after the event dispatcher bundle's
    :class:`~xtr_event_dispatcher.bundle.RegisterListenersPass`, which works
    out both sets of listeners.
    """

    __slots__ = ()

    def process(self, builder: ContainerBuilder) -> None:
        """Merge the main dispatcher's security listeners into each firewall's."""
        main = _listeners_of(builder, None)
        for firewall in builder.get_extension_config(SecurityConfig).firewalls:
            name = firewall_dispatcher_name(firewall)
            if not builder.has_definition(EventDispatcherInterface, name):
                continue
            own = _listeners_of(builder, name)
            _ = builder.get_definition(EventDispatcherInterface, name).set_argument(
                "listeners", own.with_listeners_of(main, _BUBBLING_EVENTS)
            )


def _listeners_of(builder: ContainerBuilder, name: str | None) -> ListenerMap:
    """Return the listeners RegisterListenersPass handed the dispatcher ``name``."""
    arguments = builder.get_definition(EventDispatcherInterface, name).get_arguments()
    return cast("ListenerMap", arguments["listeners"])
