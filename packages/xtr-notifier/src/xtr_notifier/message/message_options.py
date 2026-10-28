"""Provider-specific options, rendered to a value that crosses a message bus."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass, field

__all__ = ["MessageOptions"]


@dataclass(frozen=True, slots=True)
class MessageOptions:
    """What a provider needs beyond a subject — blocks, buttons, a parse mode — as plain data.

    A provider's options builder (``SlackOptions``, ``TelegramOptions``) renders
    one of these with its ``to_options()``. Keeping the rendered form a frozen
    value of JSON data, rather than the builder itself, is what lets a message
    carrying it be queued on a message bus and sent by another process: the
    transport there reads the same values back.

    A transport sends options only when their ``kind`` is its own, so a message
    rendered for one provider is never sent to another with options it would
    misread.

    Attributes:
        kind: Which provider's options these are (``"slack"``, ``"telegram"``).
        recipient_id: Who the message goes to on that provider — a channel, a
            chat — or ``None`` to leave it to the transport's default.
        values: The provider's options, as JSON data only — strings, numbers,
            booleans, ``None``, lists and string-keyed mappings of them — so
            they survive the trip through a message bus.
    """

    kind: str
    recipient_id: str | None = None
    values: Mapping[str, object] = field(default_factory=dict[str, object])

    def __post_init__(self) -> None:
        """Take a copy of ``values``, so the caller's mapping cannot change these options."""
        object.__setattr__(self, "values", dict(self.values))

    def with_recipient_id(self, recipient_id: str | None) -> MessageOptions:
        """Return a copy going to ``recipient_id`` instead."""
        return dataclasses.replace(self, recipient_id=recipient_id)
