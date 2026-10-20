"""A channel that records what it was asked to send."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_notifier.channel import ChannelInterface

if TYPE_CHECKING:
    from xtr_notifier.notification import Notification
    from xtr_notifier.recipient import RecipientInterface

__all__ = ["RecordingChannel"]


@final
class RecordingChannel(ChannelInterface):
    """Records each ``(notification, recipient, transport_name)`` it is handed."""

    def __init__(self, supports: bool = True) -> None:
        self.notified: list[tuple[Notification, RecipientInterface, str | None]] = []
        self._supports = supports

    @override
    async def notify(
        self,
        notification: Notification,
        recipient: RecipientInterface,
        transport_name: str | None = None,
    ) -> None:
        self.notified.append((notification, recipient, transport_name))

    @override
    def supports(self, notification: Notification, recipient: RecipientInterface) -> bool:
        return self._supports
