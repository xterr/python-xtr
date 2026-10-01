"""The name a firewall's own event dispatcher is registered under."""

from __future__ import annotations

__all__ = ["firewall_dispatcher_name"]


def firewall_dispatcher_name(firewall: str) -> str:
    """Return the name of the dispatcher ``firewall`` dispatches its security events on.

    The qualifier it is registered under, as ``EventDispatcherInterface``, and
    what a listener names to hear that firewall alone::

        @as_event_listener(dispatcher=firewall_dispatcher_name("api"))
        def on_api_login(event: LoginSuccessEvent) -> None: ...

    A listener on the main dispatcher hears every firewall's security events.
    """
    return f"security.event_dispatcher.{firewall}"
