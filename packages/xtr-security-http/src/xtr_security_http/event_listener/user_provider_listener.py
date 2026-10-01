"""The listener that gives a user badge its loader from the firewall's provider."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface

from xtr_security_http.event.check_passport_event import CheckPassportEvent

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents
    from xtr_security_core.user.user_provider_interface import UserProviderInterface

__all__ = ["UserProviderListener"]

#: The priority the provider listener runs at — before every other passport check.
PRIORITY = 2048


@final
class UserProviderListener(EventSubscriberInterface):
    """Sets a user badge's loader from the firewall's provider, when it has none.

    Runs first on the passport check, so the listeners after it — the account
    check, the credentials check — can load the user. An authenticator that
    already gave the badge a loader (a bearer handler that resolved the user
    from a token's claims) is left alone. The provider's ``load_user_by_identifier``
    is set as the loader directly, so a badge with attributes reaches an
    attributes-based provider's two-argument method and a plain provider's
    one-argument one — the badge chooses by the method's own shape.
    """

    __slots__ = ("_provider",)

    def __init__(self, provider: UserProviderInterface) -> None:
        """Record the provider a badge's loader is built from."""
        self._provider = provider

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Listen to the passport check first of all, at :data:`PRIORITY`."""
        return {CheckPassportEvent: ("check_passport", PRIORITY)}

    async def check_passport(self, event: CheckPassportEvent) -> None:
        """Give the badge the provider's loader, unless it already has one."""
        badge = event.get_passport().get_user_badge()
        if badge.get_user_loader() is None:
            badge.set_user_loader(self._provider.load_user_by_identifier)
