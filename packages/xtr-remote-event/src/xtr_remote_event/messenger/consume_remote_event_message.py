"""Asks for an event that arrived to be handed to the consumer of its source."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from xtr_messenger import as_message

from xtr_remote_event.remote_event import RemoteEvent

__all__ = ["ConsumeRemoteEventMessage"]


@as_message(name="xtr_remote_event.consume.v1")
@final
@dataclass(frozen=True, slots=True)
class ConsumeRemoteEventMessage:
    """Hand ``event`` to the consumer registered under ``type``.

    What turns receiving an event into consuming it, and the reason the two
    can happen in different processes: whatever read the event answers the
    sender at once, and the work the event asks for is done wherever this
    message is routed.

    It carries the event rather than an id to look up, because the event has
    already been read and nothing has stored it; a consumer that wants it kept
    is the one that stores it.

    Attributes:
        type: The name the consumer answering for this source is registered
            under. Separate from ``event.name`` so a payload converter can
            decide which consumer an event belongs to without rewriting the
            event it read.
        event: The event as it was read, handed on untouched.
    """

    type: str
    event: RemoteEvent
