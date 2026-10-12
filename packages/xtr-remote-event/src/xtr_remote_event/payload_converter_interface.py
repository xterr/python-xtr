"""What turns a payload as it arrived into an event."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .remote_event import RemoteEvent

__all__ = ["PayloadConverterInterface"]


@runtime_checkable
class PayloadConverterInterface(Protocol):
    """Reads one sender's payload as an event of a name and an id.

    This is where a sender's vocabulary is translated and nowhere else: the
    name a consumer is declared under is decided here, so adding a sender is
    writing one converter rather than touching whatever dispatches events.

    It takes the payload already decoded — reading the bytes, and deciding
    whether they are to be trusted at all, belongs to whatever received them —
    and it is synchronous, because translating a mapping reaches for nothing.
    """

    def convert(self, payload: Mapping[str, object]) -> RemoteEvent:
        """Return the event ``payload`` describes.

        Args:
            payload: The sender's payload, decoded.

        Raises:
            ParseError: If the payload is not one this converter can read — a
                field missing, or a value that cannot be a name or an id.
        """
        ...
