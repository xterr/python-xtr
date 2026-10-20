"""What sends a message to a provider."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_notifier.message import MessageInterface, SentMessage

__all__ = ["TransportInterface"]


@runtime_checkable
class TransportInterface(Protocol):
    """Sends messages to one provider — or picks among several.

    Its string form names it in errors, logs and :class:`SentMessage
    <xtr_notifier.message.SentMessage>` reports, so it must never carry a
    credential: ``slack://slack.com?channel=ops``, not the token.
    """

    async def send(self, message: MessageInterface) -> SentMessage:
        """Send ``message`` and report what the provider answered.

        Implementations raise :class:`~xtr_notifier.exception.TransportError`
        when the provider cannot be reached or refuses the message — the one
        failure a failover transport tries another provider for.
        """
        ...

    def supports(self, message: MessageInterface) -> bool:
        """Tell whether ``message`` is something this transport sends."""
        ...
