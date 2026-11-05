---
name: xtr-remote-event
description: How to hand an event that came from another system to the code that handles it with xtr-remote-event — one RemoteEvent value type at the base of a class hierarchy, a one-method consumer declared with as_remote_event_consumer, a ConsumerLocator that finds it by source name, and ConsumeRemoteEventMessage so the work happens on a worker. Use when a delivery report, a payment notice, a provider callback or any inbound event needs routing to the code that handles that sender; when writing or declaring a consumer; when deriving an event class of your own that must cross a bus as itself; when translating a sender's payload with a PayloadConverterInterface; when adding RemoteEventBundle to an application; or when a webhook read by xtr-webhook has to reach a consumer.
---

# xtr-remote-event

An event from elsewhere arrives in whatever shape its sender chose. Once it is read, what the
application does with it is always the same: hand it to the code that handles events from that
sender. This package is that last step and nothing else.

## Quick reference

- `RemoteEvent(name, id, payload)` — frozen, three fields, no behaviour. `name` is the source
  and decides who is handed it; `payload` is a `dict[str, object]` of JSON data as it arrived.
- `RemoteEvent` is the base of a class hierarchy (xtr-serializer's `@discriminator_map()`, wire
  key `"$type"`, its own name `"remote_event"`). Derive a class and register its name with
  `@discriminator_name("<name>")` — it then crosses a bus as itself. A webhook's HTTP body
  carries only the payload, so over HTTP a receiver gets a plain `RemoteEvent`.
- `@as_remote_event_consumer("<source>")` on a class with `async def consume(self, event)`.
  Stack it for several sources.
- `ConsumerLocator({"<source>": consumer})` → `await locator.get("<source>")`. Also takes a
  `ServiceProviderInterface`, which is what the bundle gives it.
- `ConsumeRemoteEventMessage(type, event)` + `ConsumeRemoteEventHandler(locator)` move the work
  onto a worker through [xtr-messenger](https://github.com/xterr/python-xtr).
- `PayloadConverterInterface.convert(payload)` → `RemoteEvent`. Synchronous, takes the payload
  already decoded.
- `MailerDeliveryEvent` / `MailerEngagementEvent` — a mail provider's reports, both
  `AbstractMailerEvent`s: a `RemoteEvent` plus keyword-only `date` (required), `recipient_email`,
  `metadata` and `tags`; a delivery adds `reason`. `name` is one of the class's constants.
  Registered as `"mailer_delivery"` and `"mailer_engagement"`, so each crosses a bus as itself.
- In an application, with xtr-dependency-injection installed beside the package (it is not a
  dependency): activate `RemoteEventBundle`, declare consumers where they live, route
  `ConsumeRemoteEventMessage`. There is no configuration module. Without the container, build the
  `ConsumerLocator` over your consumers yourself; only `xtr_remote_event.bundle` needs it.
- Every error derives from `RemoteEventError` but one: building `AbstractMailerEvent` itself
  raises `TypeError`.

## Derive an event of your own

```python
from dataclasses import dataclass, field

from xtr_remote_event import RemoteEvent
from xtr_serializer import ZonedDateTime, discriminator_name


@dataclass(frozen=True, slots=True)
class Recipient:
    address: str


@discriminator_name("delivery_report")
@dataclass(frozen=True, slots=True)
class DeliveryReport(RemoteEvent):
    delivered_at: ZonedDateTime
    recipient: Recipient
    tags: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict[str, str])
```

- Written as `{"$type": "delivery_report", "name": ..., "id": ..., "payload": ..., ...}` wherever
  a field declares `RemoteEvent`, and read back a `DeliveryReport` with every nested value of its
  declared type.
- `@discriminator_name` goes on top of `@dataclass`. Register at import, in the module defining
  the class, before any message holding an event is written or read: a name given later raises
  `MappingError`.
- A derived class with no name is refused when written (`MessageEncodingFailedError` on a bus) —
  never written as its base.
- Put typed values in fields of the derived class, not in `payload`: `payload` holds JSON data
  only. Declare a date that must keep its zone `ZonedDateTime`; a plain `datetime` keeps its
  offset.
- Data is untrusted: an unknown tag, the name of another hierarchy's class, a missing tag or a
  value that does not fit is refused — on a bus with `MessageDecodingFailedError`, which never
  repeats the data.
- Every registered class is part of one schema. A class pydantic cannot build — a field typed
  `DatePoint` (declare it `datetime`), an annotation imported only under `TYPE_CHECKING` — makes
  every message declaring `RemoteEvent` refused, and the error names neither class nor field.

## Declare a consumer

```python
from xtr_remote_event import RemoteEvent, as_remote_event_consumer


@as_remote_event_consumer("acme")
class AcmeConsumer:
    async def consume(self, event: RemoteEvent) -> None:
        await do_something_with(event.payload)
```

- The declaration is written onto the class, so whatever gathers consumers finds it where it
  finds the class — a container's scan sees it, and a test that declares one leaves nothing
  behind for the next.
- Stack the decorator for a consumer answering for several sources. The names are recorded from
  the one nearest the class outwards, so reading them back reads as it was written.
- One method, returning nothing: a consumer is the end of the line, not a step in a chain.
- Async, because consuming is where the work is — a row written, a mail sent, a call back.
- An empty name, or a class with no `consume()`, raises `InvalidArgumentError` where the
  declaration is written, not when the first event arrives.
- Read it back with `remote_event_consumers_declared_on(cls)` from `xtr_remote_event.decorator`.
  Only what was written on that class: a subclass answers for nothing until it is decorated too.

## Find the consumer of a source

```python
from xtr_remote_event import ConsumerLocator

consumers = ConsumerLocator({"acme": AcmeConsumer(), "stripe": PaymentConsumer()})

consumer = await consumers.get("acme")
await consumer.consume(event)
```

`consumers.has(name)` asks first; `provided_services()` reports what it covers. A source nothing
is registered under raises `LogicError` with
`Unable to find a consumer for message of type "<name>".`

Pass a `ServiceProviderInterface` instead of a mapping — the bundle passes a container-backed
one — and each consumer is built, with its dependencies, when an event for it first arrives.

## Consume on a worker

```python
from xtr_messenger import HandlersLocator, MessageBusConfig, MessageBusFactory, TransportConfig
from xtr_remote_event import ConsumerLocator
from xtr_remote_event.messenger import ConsumeRemoteEventHandler, ConsumeRemoteEventMessage

handlers = HandlersLocator()
_ = handlers.register(
    ConsumeRemoteEventMessage,
    ConsumeRemoteEventHandler(ConsumerLocator({"acme": AcmeConsumer()})),
)

bus = MessageBusFactory(
    MessageBusConfig(
        transports={"sync": TransportConfig("sync://")},
        routing={ConsumeRemoteEventMessage: "sync"},
    ),
    handlers=handlers,
).bus()

_ = await bus.dispatch(ConsumeRemoteEventMessage("acme", event))
```

- The message is declared `"xtr_remote_event.consume.v1"`, so it keeps its name across a deploy.
- `type` is separate from `event.name`, so a payload converter can decide which consumer an
  event belongs to without rewriting the event it read.
- It carries the event rather than an id, because nothing has stored it. A consumer that wants
  it kept is the one that stores it.
- `"sync://"` handles in the dispatching process; a broker transport hands it to a worker.
- Through a serializing transport the event arrives as its own class — `type(event)` is the
  derived class it was dispatched with.
- In a wired application the bundle registers the handler, so you never register it yourself.

## Translate a sender's payload

```python
from collections.abc import Mapping

from xtr_remote_event import PayloadConverterInterface, RemoteEvent
from xtr_remote_event.exception import ParseError


class AcmeConverter(PayloadConverterInterface):
    def convert(self, payload: Mapping[str, object]) -> RemoteEvent:
        kind = payload.get("kind")
        if not isinstance(kind, str):
            raise ParseError('The payload has no "kind" naming the event.')
        event_id = payload.get("id")
        if not isinstance(event_id, str | int):
            raise ParseError('The payload has no "id" identifying the event.')
        return RemoteEvent(kind, str(event_id), dict(payload))
```

This is where a sender's vocabulary is translated and nowhere else: adding a sender is writing
one converter rather than touching whatever dispatches events. It takes the payload already
decoded — reading the bytes, and deciding whether they are to be trusted at all, belongs to
whatever received them — and it is synchronous, because translating a mapping reaches for
nothing.

## Report what became of a mail

```python
from collections.abc import Mapping
from datetime import UTC, datetime

from xtr_remote_event import MailerDeliveryEvent, PayloadConverterInterface, RemoteEvent
from xtr_remote_event.exception import ParseError

_DELIVERY = {"delivered": MailerDeliveryEvent.DELIVERED, "bounced": MailerDeliveryEvent.BOUNCE}


class AcmeMailConverter(PayloadConverterInterface):
    def convert(self, payload: Mapping[str, object]) -> RemoteEvent:
        name = _DELIVERY.get(str(payload.get("event")))
        if name is None:
            raise ParseError(f'Unsupported event "{payload.get("event")}".')
        try:
            event_id = str(payload["id"])
            date = datetime.fromtimestamp(float(str(payload["timestamp"])), UTC)
        except (KeyError, ValueError, OverflowError, OSError) as error:
            raise ParseError(f"Unreadable delivery report: {error!r}.") from error
        return MailerDeliveryEvent(
            name,
            event_id,
            dict(payload),
            date=date,
            recipient_email=str(payload.get("recipient", "")),
            reason=str(payload.get("reason", "")),
        )
```

- `name` is one of the class's constants, never the provider's word: a delivery is `RECEIVED`,
  `DROPPED`, `DELIVERED`, `DEFERRED` or `BOUNCE`; an engagement (`MailerEngagementEvent`) is
  `OPEN`, `CLICK`, `SPAM` or `UNSUBSCRIBE`. The converter translates, so consumers never do.
- The three `RemoteEvent` fields stay positional; everything a mailer event adds is a keyword.
  `date` is when the provider says it happened, not when the report arrived.
- `date` is a plain `datetime`: give it in UTC, as providers report it. It keeps its offset on a
  bus, not a zone's name, and one in the hour the clocks repeat is refused when written.
- `metadata` holds JSON data, as `payload` does.
- A payload is the sender's, so whatever reading it raises becomes a `ParseError`: `KeyError` for
  a missing field, and `ValueError`, `OverflowError` or `OSError` for a timestamp that is not a
  number or not a time `datetime.fromtimestamp` can convert.
- `AbstractMailerEvent` holds what both share; building it itself raises `TypeError`.

## Testing

A consumer is a class with one method, so test it directly:

```python
import pytest
from xtr_remote_event import ConsumerLocator, RemoteEvent


@pytest.mark.anyio
async def test_a_paid_order_is_marked_paid() -> None:
    consumer = AcmeConsumer(orders)

    await consumer.consume(RemoteEvent("order.paid", "evt_1", {"order_id": "7"}))

    assert await orders.is_paid("7")
```

- `RemoteEvent` is a frozen dataclass, so two with the same three fields compare equal — assert
  on the whole event rather than field by field.
- For an event class of your own, round-trip it through
  `TransportConfig("in-memory://?serialize=true")` and assert both `==` and
  `type(received.event) is DeliveryReport`. A dataclass compares the exact class, so a derived
  event never equals its base, even one that adds no field.
- For the handler, build a `ConsumerLocator` over a recording consumer and assert what it was
  handed. No bus is needed: the handler is callable.
- A missing consumer is testable without a container:
  `pytest.raises(LogicError)` on `locator.get("absent")`.
- Declaring a consumer in a test leaves nothing behind, because the declaration lives on the
  class.

## Use in an application

`uv run xtr-recipes recipes:sync` applies the recipe shipped with this package: it lists
`RemoteEventBundle`. That is all a recipe can do here; it prints the two steps below it cannot.

1. **Install** — `uv add xtr-remote-event xtr-dependency-injection`: the bundle needs the
   container installed beside it, never as an extra. There are no extras.
2. **Activate** — `RemoteEventBundle: {"all": True}` in `BUNDLES` in `<app>/config/bundles.py`
   (`from xtr_remote_event.bundle import RemoteEventBundle`). The xtr-webhook bundle requires
   this one, and a sync lists it whether or not webhook is installed.
3. **Brings along** — the messenger bundle, always: the handler is registered on its bus; and the
   serializer bundle through it, which writes the message.
4. **Configure** — nothing. `RemoteEventConfig` takes no value, because which consumer answers
   for which source is declared beside the class that consumes.
5. **Environment** — nothing. **Ignore** — nothing.
6. **Use** — declare consumers where they live; each is a service, so it asks for what it needs:

   ```python
   # app/consumer/payment_consumer.py
   from xtr_remote_event import RemoteEvent
   from xtr_remote_event.decorator import as_remote_event_consumer


   @as_remote_event_consumer("acme")
   class PaymentConsumer:
       def __init__(self, orders: OrderRepository) -> None:
           self._orders = orders

       async def consume(self, event: RemoteEvent) -> None:
           await self._orders.mark_paid(event.payload["order_id"])
   ```

   A class declared for two sources is registered once, so what it remembers between events does
   not depend on which name the event arrived under.
7. **Consume elsewhere** — route `ConsumeRemoteEventMessage` to a transport in
   `<app>/config/packages/messenger.py` to handle it on a worker; left unrouted it is handled in the
   process that dispatched it.
8. **Check** — `debug:bundles` shows `remote_event` as `listed` and `active`.
9. **Remove** — drop the `BUNDLES` entry, then `uv remove xtr-remote-event` — unless xtr-webhook
   is installed, which depends on it.

## Errors

Everything derives from `RemoteEventError`, with one exception: the `TypeError` raised when `AbstractMailerEvent` itself is built, a programming error like building any abstract type.

| Error | Raised when | Also a |
| --- | --- | --- |
| `InvalidArgumentError` | a value cannot be used — an empty consumer name, a class with no `consume()` | `ValueError` |
| `ParseError` | a converter cannot read a payload as an event | `InvalidArgumentError` |
| `LogicError` | nothing is registered for a source, or what is registered is not a consumer | `RuntimeError` |
| `TypeError` | `AbstractMailerEvent` itself is built — a programming error, as with any abstract type | — (not a `RemoteEventError`; the message is `"AbstractMailerEvent" is abstract: build a "MailerDeliveryEvent" or a "MailerEngagementEvent" instead.`) |

A `ParseError` is the sender's doing, so the answer is to tell the sender. A `LogicError` is
wiring the application got wrong, and is said where the event would otherwise be lost.
An event that cannot be written or read is refused by what carries it: on a bus,
`MessageEncodingFailedError` / `MessageDecodingFailedError` from xtr-messenger.

## Do not

- Do not mutate a `RemoteEvent` or its `payload` in a consumer: the event is a record of
  something that already happened, and the next consumer is given the same one. Copy it first.
- Do not inject the container into a consumer or into the handler. The handler takes a
  `ConsumerLocator`, which answers the only question it has.
- Do not keep a table of source names in the application: declare each consumer beside the class
  that consumes, which is the one place that cannot drift.
- Do not rely on a decorated base class to declare its subclasses — it does not, deliberately,
  or every derived class would answer for its parent's sources.
- Do not put a provider's own vocabulary in a consumer. Translate in a
  `PayloadConverterInterface` and keep the consumer about what the application does.
- Do not expect `event.name` and a message's `type` to be the same string; they are separate on
  purpose.
- Do not derive an event class without `@discriminator_name`, and do not register the name lazily
  — in a function or a test body. Name it at import, beside the class.
- Do not put dates, decimals or objects in `payload`; declare them as fields of a derived class.
