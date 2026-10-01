"""A listener that names the ``api`` firewall's dispatcher, so only that firewall runs it."""

from __future__ import annotations

from xtr_event_dispatcher import as_event_listener
from xtr_security_http.event.login_success_event import LoginSuccessEvent

from xtr_security.bundle import firewall_dispatcher_name

__all__ = ["on_api_login"]


@as_event_listener(dispatcher=firewall_dispatcher_name("api"))
def on_api_login(event: LoginSuccessEvent) -> None:
    """Hear a login on the ``api`` firewall alone."""
    del event
