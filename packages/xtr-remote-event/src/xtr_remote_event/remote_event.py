"""An event that came from another system, as one value."""

from __future__ import annotations

from dataclasses import dataclass

from xtr_serializer import discriminator_map, discriminator_name

__all__ = ["RemoteEvent"]


@discriminator_name("remote_event")
@discriminator_map()
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
    value of your own from it when something has to change.

    The base of a class hierarchy, so an event of a class derived from it
    travels as that class wherever a field declares ``RemoteEvent`` — in a
    message on a bus, above all. Each value is written with its
    class's name under ``"$type"``, and read back only as a class of this
    hierarchy that registered that name: this one is ``"remote_event"``. A
    source worth naming gets a type of its own over the same three fields,
    registered with :func:`~xtr_serializer.discriminator_name` where it is
    defined::

        @discriminator_name("payment_captured")
        @dataclass(frozen=True, slots=True)
        class PaymentCaptured(RemoteEvent):
            amount: Decimal

    A derived class without a name is refused when it is written, rather
    than written as this one.

    Attributes:
        name: The source this came from — the name a consumer is declared
            under, and what decides who is handed the event.
        id: What the sender calls this event, so one arriving twice can be
            recognised as the same one.
        payload: The body as it arrived, read no further than the two fields
            above, and to be read rather than written: the freeze binds this
            field, not the dict behind it. It holds JSON data — strings,
            numbers, booleans, ``None``, lists and dicts of them; a value of
            any other type belongs in a field of a derived class, which
            declares its type.
    """

    name: str
    id: str
    payload: dict[str, object]
