"""The listeners a firewall's remember-me cookies are answered by.

The cookie itself is staged and spent by the handler the authenticator
holds; what the wiring adds is the flow around it. A successful login is
asked whether it asked to be remembered — the conditions listener, ahead of
the one that sets the cookie — and the endings that must drop the cookie
(a failed login, a logout, a deauthentication) clear it. The cookie the
handler staged reaches the response only through the response listener on
the main dispatcher: the kernel's response event is a lifecycle event, one
per application, and the listener itself holds nothing of the request.

The handler holds the firewall's user provider, which may be one of the
request's services, so the listeners that reach it — the one setting the
cookie and the one clearing it — are per-call functions
:class:`~xtr_security.bundle.RegisterPerCallListenersPass` places, not
services the dispatcher keeps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_dependency_injection import named_factory
from xtr_event_dispatcher.bundle import SUBSCRIBER_TAG
from xtr_security_http import (
    CheckRememberMeConditionsListener,
    PersistentRememberMeHandler,
    ResponseListener,
    SignatureRememberMeHandler,
)

from xtr_security.bundle.firewall_dispatcher_name import firewall_dispatcher_name
from xtr_security.bundle.remember_me_config import RememberMeConfig

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_dependency_injection import ServiceConfigurator

__all__ = [
    "register_remember_me_listeners",
    "register_remember_me_response_listener",
    "remember_me_handler_type",
]


def register_remember_me_listeners(
    services: ServiceConfigurator,
    name: str,
    settings: RememberMeConfig,
) -> None:
    """Register the conditions listener on the firewall's own dispatcher.

    The conditions listener runs first, at ``-32``: it reads the request's
    ask and enables the passport's badge when there is one, so the listener
    that sets the cookie — at ``-64``, behind it — only ever sets it for a
    login that asked. It holds nothing of the request, so it is a subscriber
    of the firewall's dispatcher, where the manager announces the login; the
    listeners that set and clear the cookie are placed per call.
    """
    dispatcher = firewall_dispatcher_name(name)
    options = settings.to_options()

    def conditions_listener() -> CheckRememberMeConditionsListener:
        """Build the listener reading the request's ask to be remembered."""
        return CheckRememberMeConditionsListener(options)

    conditions_listener.__annotations__ = {"return": CheckRememberMeConditionsListener}
    _ = services.set(
        named_factory(conditions_listener, f"check_remember_me_conditions_listener_{name}"),
        qualifier=dispatcher,
    ).add_tag(SUBSCRIBER_TAG, dispatcher=dispatcher)


def remember_me_handler_type(settings: RememberMeConfig) -> type:
    """Return the class of the handler the configuration asks the cookies be held by."""
    if settings.handler == "signature":
        return SignatureRememberMeHandler
    return PersistentRememberMeHandler


def register_remember_me_response_listener(services: ServiceConfigurator) -> None:
    """Register, once, the listener moving a staged cookie onto the response.

    One service for the application, on the main dispatcher: the kernel's
    response event is a lifecycle event, and the listener holds nothing of
    the request — the cookie it moves is staged on the request's own state,
    which the event carries.
    """
    _ = services.set(ResponseListener).add_tag(SUBSCRIBER_TAG)


def remember_me_settings_of(
    authenticators: Sequence[object],
) -> RememberMeConfig | None:
    """Return the firewall's remember-me configuration, or ``None`` when it has none."""
    for authenticator in authenticators:
        if isinstance(authenticator, RememberMeConfig):
            return authenticator
    return None
