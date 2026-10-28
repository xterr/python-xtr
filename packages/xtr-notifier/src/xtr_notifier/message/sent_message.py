"""What a transport reports back about a message it sent."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .message_interface import MessageInterface

__all__ = ["SentMessage"]


class SentMessage:
    """A message a transport sent, with what the provider answered.

    Not final: a provider whose answer is worth more than an id — a Slack
    message's channel and timestamp, needed to edit it later — returns a
    subclass carrying it.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_info", "_message_id", "_original", "_transport")

    _original: MessageInterface
    _transport: str
    _info: dict[str, object]
    _message_id: str | None

    def __init__(
        self,
        original: MessageInterface,
        transport: str,
        info: Mapping[str, object] | None = None,
        message_id: str | None = None,
    ) -> None:
        """Record what was sent, and through what.

        Args:
            original: The message that was sent.
            transport: The string form of the transport that sent it.
            info: Anything else the transport knows about the send.
            message_id: The id the provider gave the message, when it gave one.
        """
        self._original = original
        self._transport = transport
        self._info = {} if info is None else dict(info)
        self._message_id = message_id

    @property
    def original_message(self) -> MessageInterface:
        """The message that was sent."""
        return self._original

    @property
    def transport(self) -> str:
        """The string form of the transport that sent it."""
        return self._transport

    @property
    def message_id(self) -> str | None:
        """The id the provider gave the message, or ``None``."""
        return self._message_id

    @message_id.setter
    def message_id(self, message_id: str | None) -> None:
        self._message_id = message_id

    @property
    def info(self) -> Mapping[str, object]:
        """Anything else the transport knows about the send."""
        return self._info

    def get_info(self, key: str) -> object:
        """Return the info under ``key``, or ``None`` when there is none."""
        return self._info.get(key)
