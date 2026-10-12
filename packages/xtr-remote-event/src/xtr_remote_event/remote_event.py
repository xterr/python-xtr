"""An event that came from another system, as one value."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["RemoteEvent"]


@dataclass(frozen=True, slots=True)
class RemoteEvent:
    """What arrived from elsewhere: where it came from, which event it is, and its body.

    Three fields and no behaviour, on purpose. Whatever read the event has
    already answered the only two questions this library needs — which source
    this is, and which of that source's events — and everything past them
    differs with every sender, so it stays in the payload for the consumer
    that understands it.

    Frozen, because an event is a record of something that already happened.
    What the freeze protects is the three bindings: no consumer can point an
    event it was handed at a different source, id or payload. It does not reach
    into what they hold — ``payload`` is an ordinary dict — so a consumer that
    writes into the payload does change the body every later consumer reads,
    and nothing here prevents it. Treat the payload as read-only, and build a
    value of your own from it when something has to change. Open to deriving
    from, so a source worth naming can have a type of its own over the same
    three fields.

    Attributes:
        name: The source this came from — the name a consumer is declared
            under, and what decides who is handed the event.
        id: What the sender calls this event, so one arriving twice can be
            recognised as the same one.
        payload: The body as it arrived, read no further than the two fields
            above, and to be read rather than written: the freeze binds this
            field, not the dict behind it.
    """

    name: str
    id: str
    payload: dict[str, object]
