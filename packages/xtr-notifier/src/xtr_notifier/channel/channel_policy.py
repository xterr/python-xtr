"""Channels by importance, from configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_notifier.exception import InvalidArgumentError

from .channel_policy_interface import ChannelPolicyInterface

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_notifier.notification import Importance

__all__ = ["ChannelPolicy"]


@final
class ChannelPolicy(ChannelPolicyInterface):
    """The channels each importance goes to, as configured.

    ``ChannelPolicy({"urgent": ["sms", "chat/slack"], "high": ["chat/slack"]})``
    texts urgent notifications and posts them to Slack, and only posts the
    high ones. Keyed by the importance's string value, so the mapping can come
    straight from configuration.
    """

    __slots__ = ("_policy",)

    def __init__(self, policy: Mapping[str, Sequence[str]]) -> None:
        """Send each importance named in ``policy`` to the channels listed for it."""
        self._policy: dict[str, tuple[str, ...]] = {
            importance: tuple(channels) for importance, channels in policy.items()
        }

    @override
    def get_channels(self, importance: Importance) -> tuple[str, ...]:
        """Return the channels configured for ``importance``.

        Raises:
            InvalidArgumentError: If the policy says nothing about ``importance``.
        """
        channels = self._policy.get(importance.value)
        if channels is None:
            raise InvalidArgumentError(
                f'Importance "{importance.value}" is not defined in the Policy.'
            )
        return channels
