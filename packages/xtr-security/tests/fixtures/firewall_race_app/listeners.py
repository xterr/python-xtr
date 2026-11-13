"""A passport listener of the ``api`` firewall that holds each login until a test lets it go.

It runs ahead of the credentials check, which the firewall's dispatcher holds
as a listener built the first time a login reaches it. Each login is named by
the user it is for: the listener signals its arrival and waits for its
release, so a test decides which login reaches the credentials check first.
"""

from __future__ import annotations

import asyncio

from xtr_event_dispatcher import as_event_listener
from xtr_security_http import UserBadge
from xtr_security_http.event.check_passport_event import CheckPassportEvent

from xtr_security.bundle import firewall_dispatcher_name

__all__ = ["ARRIVED", "RELEASE", "hold_the_login"]

ARRIVED: dict[str, asyncio.Event] = {}
"""Set when the login of that user reaches the listener."""

RELEASE: dict[str, asyncio.Event] = {}
"""Set by the test to let the login of that user go on to its checks."""


@as_event_listener(priority=1024, dispatcher=firewall_dispatcher_name("api"))
async def hold_the_login(event: CheckPassportEvent) -> None:
    """Hold the login until the test releases the user it is for."""
    badge = event.get_passport().get_badge(UserBadge)
    assert badge is not None
    name = badge.get_user_identifier()
    ARRIVED[name].set()
    _ = await RELEASE[name].wait()
