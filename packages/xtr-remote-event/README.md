<div align="center">

# xtr-remote-event

**Events received from another system, as one value type, handed to the consumer registered under their source's name — directly or through a message bus.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="asyncio" src="https://img.shields.io/badge/asyncio-native-1f6feb">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

An event from elsewhere — a delivery report, a payment notice, a message from a provider —
arrives in whatever shape its sender chose. Once it is read, though, what the application does
with it is always the same: hand it to the code that handles events from that sender.

This package is that last step, and nothing else: one value type for the event, a one-method
contract for the consumer, a decorator naming which sources a consumer answers for, and a
message so the work happens on a worker rather than in the request that received it.

## Install

```sh
uv add xtr-remote-event                            # the event, the consumer contract, the decorator
uv add xtr-remote-event xtr-dependency-injection   # + the container, for the RemoteEventBundle
```

The container is not a dependency: the bundle is used when
[xtr-dependency-injection](../xtr-dependency-injection) is installed beside the package, never as
an extra, and the event, the consumers and the message work without it, as the
[Quick start](#quick-start) shows.
[xtr-serializer](../xtr-serializer) is: it is what carries an event as its own class.

## Quick start

A consumer is a class with one method, declared with the name of the source whose events it
answers for:

```python
import asyncio

from xtr_remote_event import ConsumerLocator, RemoteEvent, as_remote_event_consumer


@as_remote_event_consumer("acme")
class AcmeConsumer:
    async def consume(self, event: RemoteEvent) -> None:
        print(f"{event.name} {event.id} {event.payload}")


async def main() -> None:
    consumers = ConsumerLocator({"acme": AcmeConsumer()})
    consumer = await consumers.get("acme")
    await consumer.consume(RemoteEvent("order.paid", "evt_1", {"total": 4200}))


asyncio.run(main())
```

A `RemoteEvent` is three fields and no behaviour: `name` (the source, and what decides who is
handed it), `id` (what the sender calls this event) and `payload` (the body as it arrived). It
is frozen, so no consumer can rebind `name`, `id` or `payload` on the event; `payload` is an
ordinary dict, though, and the next consumer is handed the same event, so every consumer must treat
the payload as read-only.

## Events of your own

`RemoteEvent` is the base of a class hierarchy, declared with xtr-serializer's
`@discriminator_map()`. Derive a class for a source worth naming, and register the name its
values are written under:

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

Wherever a field declares `RemoteEvent` — the event in `ConsumeRemoteEventMessage`, the one in
[xtr-webhook](../xtr-webhook)'s `SendWebhookMessage` — a `DeliveryReport` is written with `"$type":
"delivery_report"` beside its fields, and read back a `DeliveryReport`: its dates, its nested
`Recipient`, its tuple and its dict as they left. A plain `RemoteEvent` is written under
`"remote_event"`. A webhook's HTTP body is the event's payload alone, so a receiver over HTTP
gets a plain `RemoteEvent` — see xtr-webhook's
[Known limitations](../xtr-webhook#known-limitations).

- Register the name where the class is defined, at import: a name is refused once a type holding
  the hierarchy has been used, so the module must be imported before the first message holding
  an event is sent or read. Choose a name that stays when the class moves.
- A derived class with no name is refused when it is written — `MessageEncodingFailedError` from
  the bus — rather than written as its base and read back without its fields.
- `payload` holds JSON data as it arrived. A value of any other type, a date above all, belongs in
  a field of a derived class, which declares its type; in `payload` it is refused when written.
- A datetime field keeps its offset; one that must keep its zone, and tell the two hours apart on
  the night the clocks go back, is declared `ZonedDateTime`.
- What is read is untrusted: a tag no class of the hierarchy registered — an unknown name, the
  name of a class of another hierarchy, no tag at all — is refused, and so is a value that does
  not fit the class its tag names. On a bus that is the messenger's `MessageDecodingFailedError`,
  which never repeats what it was handed.

## Consumers

`as_remote_event_consumer` writes the declaration onto the class itself, so whatever gathers
consumers finds it where it finds the class — a container's scan sees it, and a test that
declares one leaves nothing behind. Stack it for a consumer serving several sources:

```python
@as_remote_event_consumer("stripe")
@as_remote_event_consumer("stripe-test")
class PaymentConsumer:
    async def consume(self, event: RemoteEvent) -> None: ...
```

Read it back with `remote_event_consumers_declared_on(cls)` from `xtr_remote_event.decorator`,
which returns the names in the order they were written. Only what was written on that class —
never a base's, so a subclass answers for nothing until it is decorated too.

An empty name, or a class with no `consume()`, is refused with `InvalidArgumentError` where the
declaration is written rather than when the first event arrives.

A `ConsumerLocator` hands consumers over by source name. Build it over consumers you already
have, or over anything implementing `ServiceProviderInterface` — which is what the bundle gives
it, so each consumer is built with its dependencies only when an event for it first arrives.
Asking for a source nothing is registered under raises `LogicError`.

## Through the message bus

`ConsumeRemoteEventMessage(type, event)` is what turns receiving an event into consuming it:
whatever read the event answers its sender at once, and the work happens wherever the message is
routed. `ConsumeRemoteEventHandler` looks the consumer up and hands it the event.

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

_ = await bus.dispatch(ConsumeRemoteEventMessage("acme", RemoteEvent("order.paid", "evt_1", {})))
```

The message's `type` is separate from `event.name`, so whatever read the event can decide which
consumer it belongs to without rewriting the event. Route the message to `"sync://"` to handle
it in the dispatching process, or to a broker transport to handle it on a worker; the message
carries the event rather than an id, because nothing has stored it yet — a consumer that wants
it kept is the one that stores it. The event crosses a broker as its own class — see
[Events of your own](#events-of-your-own).

In a wired application the bundle registers the handler, so dispatching the message never meets
the bus's no-handler error.

## Converting payloads

`PayloadConverterInterface` is where one sender's vocabulary is translated and nowhere else:
adding a sender is writing one converter rather than touching whatever dispatches events.

```python
from collections.abc import Mapping

from xtr_remote_event import PayloadConverterInterface, RemoteEvent
from xtr_remote_event.exception import ParseError


class AcmeConverter(PayloadConverterInterface):
    def convert(self, payload: Mapping[str, object]) -> RemoteEvent:
        kind = payload.get("kind")
        if not isinstance(kind, str):
            raise ParseError('The payload has no "kind" naming the event.')
        return RemoteEvent(kind, str(payload["id"]), dict(payload))
```

It takes the payload already decoded and is synchronous: reading the bytes, and deciding whether
they are to be trusted at all, belongs to whatever received them — [xtr-webhook](../xtr-webhook)
for one.

## Mailer events

Every mail provider reports what became of the messages it was handed — accepted, delivered,
bounced, opened, clicked — each in its own words. Two event types give those reports the same
fields whichever provider sent them, so a provider's converter builds one and a consumer of mail
reports is written once:

- `MailerDeliveryEvent` — where a message stands on its way to its recipient. `name` is one of
  its constants `RECEIVED`, `DROPPED`, `DELIVERED`, `DEFERRED` or `BOUNCE`, and `reason` is the
  provider's explanation, `""` when it gave none.
- `MailerEngagementEvent` — what the recipient did with it: `OPEN`, `CLICK`, `SPAM` or
  `UNSUBSCRIBE`.

Both derive from `AbstractMailerEvent`, a `RemoteEvent` with four more fields, passed by
keyword: `date` (when the provider says it happened, and required), `recipient_email`,
`metadata` (the values the mail was sent with, as the provider hands them back) and `tags`.
Building `AbstractMailerEvent` itself raises `TypeError`.

```python
from datetime import UTC, datetime

from xtr_remote_event import MailerDeliveryEvent, RemoteEvent

event: RemoteEvent = MailerDeliveryEvent(
    MailerDeliveryEvent.BOUNCE,
    "msg_42",
    {"event": "failed", "severity": "permanent"},
    date=datetime(2026, 1, 1, 9, 30, tzinfo=UTC),
    recipient_email="jane@example.com",
    metadata={"order_id": "7"},
    tags=("receipt",),
    reason="550 No such user",
)

if isinstance(event, MailerDeliveryEvent) and event.name == MailerDeliveryEvent.BOUNCE:
    print(f"{event.recipient_email} bounced: {event.reason}")
```

They are frozen like the event they derive from, and the freeze reaches as far: it binds
`metadata`, not the mapping behind it.

Both are [events of their own](#events-of-your-own), registered as `"mailer_delivery"` and
`"mailer_engagement"`: in `ConsumeRemoteEventMessage` on a serializing transport each comes back
of its own type, every field as it left. `date` is a plain `datetime`, so it keeps its offset
but not a zone's name, and one in the hour the clocks repeat is refused when written — give it in
UTC, as providers report it. `metadata` holds JSON data, as `payload` does.

## Known limitations

- **Every class registered under `RemoteEvent` is part of one schema.** One class pydantic cannot
  build — a field typed `DatePoint` (declare it `datetime`), an annotation imported only under
  `TYPE_CHECKING` — makes every message declaring `RemoteEvent` refused, and the error names
  neither the class nor the field.

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what
removing it undoes.

- **Install** — `uv add xtr-remote-event xtr-dependency-injection`: the bundle needs the
  container installed beside it, never as an extra. There are no extras.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Activate* step below: it lists
  `RemoteEventBundle`. There is nothing else for it to write — no configuration module, no
  environment variable, no ignore line. It prints the steps to declare your consumers and to
  route `ConsumeRemoteEventMessage`, neither of which a recipe can make for you.
- **Activate** — `RemoteEventBundle: {"all": True}` in `BUNDLES` in `<app>/config/bundles.py`,
  imported from `xtr_remote_event.bundle` — or nothing to do when
  [xtr-webhook](../xtr-webhook)'s bundle is listed, which requires this one.
- **Brings along** — the messenger bundle, always: the handler is registered on its bus; and the
  serializer bundle through it, which writes the message.
- **Configure** — nothing. `RemoteEventConfig` takes no value, because which consumer answers
  for which source is declared beside the class that consumes — see
  [Kernel / bundle](#kernel--bundle).
- **Environment** — nothing.
- **Ignore** — nothing.
- **Remove** — drop the `BUNDLES` entry, then `uv remove xtr-remote-event` — unless
  xtr-webhook is installed, which depends on it.
- **Check** — `debug:bundles` shows `remote_event` as `listed` and `active`.

## Kernel / bundle

With [xtr-dependency-injection](../xtr-dependency-injection) installed beside the package — it is
not a dependency, and nothing outside `xtr_remote_event.bundle` needs it — list the bundle:

```python
# app/config/bundles.py
from xtr_remote_event.bundle import RemoteEventBundle

BUNDLES = {RemoteEventBundle: {"all": True}}
```

There is no `config/packages/remote_event.py` to write. The bundle finds every class declared with
`@as_remote_event_consumer` when the container is built, registers each one as a single service
— once, however many sources it declared, so what it remembers between events does not depend
on which name the event arrived under — and registers `ConsumeRemoteEventHandler` over a
`ConsumerLocator` backed by the container.

A consumer is a service like any other, so it asks for what it needs:

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

Each is built — with its dependencies — only when an event for its source first arrives. To
consume on a worker rather than in the process that received the event, route the message in
the messenger configuration:

```python
# app/config/packages/messenger.py
from xtr_dependency_injection import configure, env
from xtr_messenger import MessageBusConfig, TransportConfig
from xtr_remote_event.messenger import ConsumeRemoteEventMessage


@configure
def messenger() -> MessageBusConfig:
    return MessageBusConfig(
        transports={"events": TransportConfig(env("MESSENGER_DSN"))},
        routing={ConsumeRemoteEventMessage: "events"},
    )
```

The zero-config path registers the locator and the handler, declares no consumer and touches no
I/O.

## Errors

Everything this library raises derives from `RemoteEventError`.

| Error | Raised when |
|---|---|
| `InvalidArgumentError` | a value cannot be used — an empty consumer name, a class with no `consume()`; also a `ValueError` |
| `ParseError` | a converter cannot read a payload as an event — the sender's doing, so tell the sender |
| `LogicError` | nothing is registered for a source, or what is registered is not a consumer; also a `RuntimeError` |

An event that cannot be written or read is refused by what carries it, not here: on a bus,
`MessageEncodingFailedError` and `MessageDecodingFailedError` from xtr-messenger.

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-remote-event`; run the commands below from there. The
`python-xtr-remote-event` repository is a read-only copy, so send issues and pull requests to
the monorepo.

```sh
uv sync
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
