"""The logout listener that clears the browser's site data."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface

from xtr_security_http.event.logout_event import LogoutEvent

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_event_dispatcher import SubscribedEvents

__all__ = ["ClearSiteDataListener"]

_HEADER_NAME: Final = "Clear-Site-Data"
"""The header that tells a browser to clear its data for the origin."""


@final
class ClearSiteDataListener(EventSubscriberInterface):
    """Answers a logout with the header that clears the site's client data.

    A logout is the moment a browser should forget what the site kept on the
    caller — its cache, its cookies, its storage — and the
    ``Clear-Site-Data`` header is the browser's own way of being told. The
    values configured are the directives the header carries, quoted and
    comma-joined the way the header reads them: ``"*"`` for everything, or
    any of ``"cache"``, ``"cookies"``, ``"storage"``,
    ``"clientHints"``, ``"executionContexts"``, ``"prefetchCache"`` and
    ``"prerenderCache"``.

    The header is set on the response a listener before this one answered
    the logout with — the default logout listener's redirect, typically —
    and only when the response does not already carry one: a listener that
    answered with its own ``Clear-Site-Data`` decided what a browser should
    clear, and that decision stands. A logout no listener answered is left
    alone — there is no response to carry the header, and the default logout
    listener is the one that answers it.
    """

    __slots__ = ("_site_data",)

    def __init__(self, site_data: Sequence[str] = ("*",)) -> None:
        """Record the site-data directives the header clears.

        Args:
            site_data: The directives the ``Clear-Site-Data`` header
                carries — ``"*"`` or a subset of the directive names —
                quoted and joined when the header is set.
        """
        self._site_data = tuple(site_data)

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Listen to a logout, beside the listeners that answer it."""
        return {LogoutEvent: "on_logout"}

    async def on_logout(self, event: LogoutEvent) -> None:
        """Set the site-data header on the response the logout was answered with.

        Runs after the default logout listener — the one that answers a
        logout nothing else answered — so a response is there to carry the
        header, and before the listeners that only clean up after it.
        """
        response = event.get_response()
        if response is None or response.has_header(_HEADER_NAME):
            return
        directives = ", ".join(f'"{one}"' for one in self._site_data)
        event.set_response(response.with_header(_HEADER_NAME, directives))
