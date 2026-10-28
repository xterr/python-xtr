"""What picks the channels a notification's importance calls for."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_notifier.notification import Importance

__all__ = ["ChannelPolicyInterface"]


@runtime_checkable
class ChannelPolicyInterface(Protocol):
    """Maps an importance to channels, for a notification that names none itself."""

    def get_channels(self, importance: Importance) -> tuple[str, ...]:
        """Return the channels ``importance`` calls for: ``"chat"``, ``"chat/slack"``, ``"sms"``."""
        ...
