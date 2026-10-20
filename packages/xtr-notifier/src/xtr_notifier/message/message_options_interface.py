"""A provider's options builder."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .message_options import MessageOptions

__all__ = ["MessageOptionsInterface"]


@runtime_checkable
class MessageOptionsInterface(Protocol):
    """Builds a provider's options, one fluent call at a time, and renders them.

    The builder is how an application writes options; the
    :class:`~xtr_notifier.message.message_options.MessageOptions` it renders is
    what a message carries. A message never holds the builder, so it stays a
    value that crosses a message bus whatever the builder looks like.
    """

    @property
    def recipient_id(self) -> str | None:
        """Who the message goes to on the provider, or ``None`` for its default."""
        ...

    def to_options(self) -> MessageOptions:
        """Render the options built so far."""
        ...
