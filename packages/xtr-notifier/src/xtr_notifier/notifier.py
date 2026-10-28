"""Sends notifications on the channels they call for."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_notifier.channel import SmsChannel
from xtr_notifier.exception import LogicError
from xtr_notifier.recipient import NoRecipient

from .admin_recipients_provider_interface import AdminRecipientsProviderInterface
from .notifier_interface import NotifierInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_service_contracts import ServiceProviderInterface

    from xtr_notifier.channel import ChannelInterface, ChannelPolicyInterface
    from xtr_notifier.notification import Notification
    from xtr_notifier.recipient import RecipientInterface

__all__ = ["Notifier"]

_CHANNELS_HINT = (
    'you should either pass channels in the constructor, override its "get_channels()" method'
)


@final
class Notifier(NotifierInterface, AdminRecipientsProviderInterface):
    """Sends each notification to each recipient, on the channels it calls for.

    The channels come from the notification — ``get_channels(recipient)`` —
    or, when it names none, from the channel policy for its importance. A
    channel name may carry a transport after a slash: ``"chat/slack"`` sends on
    the ``chat`` channel through the ``slack`` transport.

    Every channel of a recipient is checked — it exists, it can reach the
    recipient — before any of them is sent on, so a misconfigured notification
    fails whole rather than half sent.

    The channels are looked up by name, in a mapping or in a
    :class:`~xtr_service_contracts.ServiceProviderInterface` — a container's
    locator, which builds only the channels a notification uses.
    """

    __slots__ = ("_admin_recipients", "_channel_policy", "_channels")

    def __init__(
        self,
        channels: Mapping[str, ChannelInterface] | ServiceProviderInterface[ChannelInterface],
        channel_policy: ChannelPolicyInterface | None = None,
        admin_recipients: Sequence[RecipientInterface] = (),
    ) -> None:
        """Send on ``channels``, picked by ``channel_policy`` when a notification names none.

        Args:
            channels: The channels, by name (``"chat"``, ``"sms"``, ``"push"``).
            channel_policy: What picks the channels of a notification that names
                none; ``None`` refuses such a notification.
            admin_recipients: The administrators of the application.
        """
        self._channels = channels
        self._channel_policy = channel_policy
        self._admin_recipients: list[RecipientInterface] = list(admin_recipients)

    @property
    @override
    def admin_recipients(self) -> tuple[RecipientInterface, ...]:
        """The administrators, in the order they were given and added."""
        return tuple(self._admin_recipients)

    def add_admin_recipient(self, recipient: RecipientInterface) -> None:
        """Add ``recipient`` to the administrators."""
        self._admin_recipients.append(recipient)

    @override
    async def send(self, notification: Notification, *recipients: RecipientInterface) -> None:
        """Send ``notification`` to each of ``recipients``, or to nobody in particular.

        Raises:
            LogicError: If the channels cannot be determined, or one does not
                exist, cannot reach the recipient, or is ``sms`` with no recipient.
            InvalidArgumentError: If the channel policy defines nothing for the
                notification's importance.
        """
        for recipient in recipients or (NoRecipient(),):
            for channel, transport_name in await self._resolve(notification, recipient):
                await channel.notify(notification, recipient, transport_name)

    async def _resolve(
        self, notification: Notification, recipient: RecipientInterface
    ) -> list[tuple[ChannelInterface, str | None]]:
        """Return each channel to send ``notification`` to ``recipient`` on, with its transport."""
        resolved: list[tuple[ChannelInterface, str | None]] = []
        for name in self._channel_names(notification, recipient):
            channel_name, _, transport_name = name.partition("/")
            channel = await self._channel(channel_name)
            if channel is None:
                raise LogicError(f'The "{channel_name}" channel does not exist.')
            if isinstance(channel, SmsChannel) and isinstance(recipient, NoRecipient):
                raise LogicError(f'The "{channel_name}" channel needs a Recipient.')
            if not channel.supports(notification, recipient):
                raise LogicError(f'The "{channel_name}" channel is not supported.')
            resolved.append((channel, transport_name or None))
        return resolved

    def _channel_names(
        self, notification: Notification, recipient: RecipientInterface
    ) -> tuple[str, ...]:
        """Return the channels the notification names, else those the policy picks."""
        channels = notification.get_channels(recipient)
        if channels:
            return channels
        prefix = (
            "Unable to determine which channels to use to send the "
            f'"{type(notification).__name__}" notification'
        )
        if self._channel_policy is None:
            raise LogicError(f'{prefix}; {_CHANNELS_HINT}, or configure a "ChannelPolicy".')
        channels = self._channel_policy.get_channels(notification.importance)
        if not channels:
            raise LogicError(
                f'{prefix}; the "{type(self._channel_policy).__name__}" returns no channels '
                f'for importance "{notification.importance.value}"; {_CHANNELS_HINT}.'
            )
        return channels

    async def _channel(self, name: str) -> ChannelInterface | None:
        """Return the channel called ``name``, or ``None`` when there is none."""
        if isinstance(self._channels, Mapping):
            return self._channels.get(name)
        return await self._channels.get(name) if self._channels.has(name) else None
