"""What the ``orders:*`` commands print about an envelope the bus returned."""

from __future__ import annotations

from xtr_console import ConsoleStyle
from xtr_messenger import Envelope, HandledStamp, SentStamp, TransportMessageIdStamp

from bookshop.stamp.dispatch_time_stamp import DispatchTimeStamp
from bookshop.stamp.maintenance_stamp import MaintenanceStamp

__all__ = ["describe_envelope"]


def _handled(stamp: HandledStamp) -> str:
    """Name the handler, and what it returned when it returned something."""
    returned = "" if stamp.result is None else f", which returned {stamp.result!r}"
    return f"handled by {stamp.handler_name}{returned}"


def describe_envelope(io: ConsoleStyle, envelope: Envelope) -> None:
    """Print what the chain recorded on ``envelope``, stamp by stamp."""
    refused = envelope.last(MaintenanceStamp)
    if refused is not None:
        io.warning(f"{type(envelope.message).__name__} refused: {refused.reason}")
        return
    timing = envelope.last(DispatchTimeStamp)
    io.listing(
        [
            f"message: {type(envelope.message).__name__}",
            *(f"sent via {s.sender_alias}" for s in envelope.all(SentStamp)),
            *(f"transport id {s.message_id}" for s in envelope.all(TransportMessageIdStamp)),
            *(_handled(stamp) for stamp in envelope.all(HandledStamp)),
            f"dispatch took {timing.milliseconds:.2f} ms" if timing else "not timed",
        ]
    )
