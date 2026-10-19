"""The logout listener that clears the stored cross-site request forgery tokens."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface
from xtr_security_csrf.token_storage.clearable_token_storage_interface import (  # noqa: TC002 -- the container reads this constructor parameter's type at runtime
    ClearableTokenStorageInterface,
)

from xtr_security_http.event.logout_event import LogoutEvent

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents

__all__ = ["CsrfTokenClearingListener"]


@final
class CsrfTokenClearingListener(EventSubscriberInterface):
    """Clears every stored cross-site request forgery token on a logout.

    A token minted for a session answers for the requests of that session —
    a form rendered to the caller, an action they were asked to confirm —
    and a logout ends the session's say. The tokens minted under it must not
    outlive it: a value stolen before the logout would otherwise still vouch
    after it, so the storage that minted them drops them all.

    The storage is the one the firewall's cross-site request forgery
    protection minted its tokens through, and it is cleared whole: the
    listener holds no list of its own, because the storage knows what it
    minted.
    """

    __slots__ = ("_csrf_token_storage",)

    def __init__(self, csrf_token_storage: ClearableTokenStorageInterface) -> None:
        """Record the storage whose minted tokens a logout drops.

        Args:
            csrf_token_storage: The clearable token storage the firewall's
                cross-site request forgery protection minted through — the
                one whose every token a logout clears.
        """
        self._csrf_token_storage = csrf_token_storage

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Listen to a logout, beside the listeners that answer it."""
        return {LogoutEvent: "on_logout"}

    async def on_logout(self, event: LogoutEvent) -> None:
        """Drop every token the storage minted.

        The storage is the request's own — built over the session the
        request reattached — so clearing it touches nothing another request
        minted under a session of its own. The event itself is not read: the
        tokens to drop are the storage's whole say, not the logout's.
        """
        del event
        await self._csrf_token_storage.clear()
