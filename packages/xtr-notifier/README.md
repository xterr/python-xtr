<div align="center">

# xtr-notifier

**Send notifications to chat, SMS and push channels — one notification, the channels its importance or its recipient call for, any provider configured by DSN.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="asyncio" src="https://img.shields.io/badge/asyncio-native-1f6feb">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

"The disk is almost full" has to reach someone: a chat room during the day, a phone at night,
both when it is urgent. Code that says *what happened* should not also decide *which provider,
which channel, which token*. Here a notification carries a subject, a body and an importance;
the notifier picks the channels — from the notification, or from a policy keyed by its
importance — and each channel hands a message to a transport chosen by a DSN
(`slack://TOKEN@default?channel=ops`). Changing provider is changing a string.

- **Channels** — `chat`, `sms` and `push`, each built from the notification or rendered by it.
- **Transports by DSN** — one string per provider; `a || b` falls over, `a && b` takes turns.
- **Providers are libraries** — each installed beside this one and found by its DSN scheme.
- **Queueable** — messages are frozen values, so they cross a message bus and are sent by a
  worker.
- **Testable** — a logger listener records every message; `xtr_notifier.testing` asserts on it,
  and holds a provider library's transport and factory to what every provider owes.

## Install

```sh
uv add xtr-notifier
uv add "xtr-notifier[messenger]"   # queue messages through xtr-messenger
```

A provider's transport reaches it through an HTTP client: install
[xtr-http-client](../xtr-http-client), or bring any
[xtr-http-client-contracts](../xtr-http-client-contracts) implementation.

## Quick start

```python
from xtr_notifier import Notifier, Transport
from xtr_notifier.channel import ChatChannel, ChannelPolicy, SmsChannel
from xtr_notifier.notification import Importance, Notification
from xtr_notifier.recipient import Recipient
from xtr_notifier.transport import TransportFactoryDiscovery

chat = Transport(
    discovery=TransportFactoryDiscovery(TransportFactoryDiscovery.CHATTER_GROUP, http_client=client)
).from_strings({"ops": "null://null"})
texts = Transport(
    discovery=TransportFactoryDiscovery(TransportFactoryDiscovery.TEXTER_GROUP, http_client=client)
).from_strings({"sms": "null://null"})

notifier = Notifier(
    {"chat": ChatChannel(chat), "sms": SmsChannel(texts)},
    ChannelPolicy({"urgent": ["sms", "chat"], "high": ["chat"]}),
)

await notifier.send(
    Notification("Disk almost full", content="98% used on db-1", importance=Importance.URGENT),
    Recipient(phone="+3312345678"),
)
```

`null://null` sends nowhere, and needs no HTTP client: swap it for a provider's DSN once its
library is installed.

## Notifications

`Notification(subject, *, content="", importance=Importance.HIGH, emoji="", channels=(),
exception=None)` is built in one call and read through properties.

- **Channels** — `channels=["chat/slack", "sms"]` names them; the part after `/` is the
  transport. Left empty, the notifier asks its `ChannelPolicy` for the importance's channels.
- **Importance** — `Importance.URGENT`, `HIGH`, `MEDIUM`, `LOW`, a `StrEnum` whose values key
  the policy. `Notification.importance_from_level("critical")` maps a log level: critical and
  above is urgent, error high, the rest low.
- **Exceptions** — `Notification.from_exception(error, channels=...)` names the subject after
  the error and keeps its traceback; the emoji follows the importance.
- **Per recipient** — override `get_channels(recipient)`, or implement
  `as_chat_message(recipient, transport_name)`, `as_sms_message(...)` or
  `as_push_message(...)` to render a channel's message yourself (`ChatNotificationInterface`
  and friends, in `xtr_notifier.notification.<kind>_notification_interface`).

Recipients are anything with an `email` or a `phone`; `Recipient(email, phone)` is the plain one,
and `NoRecipient()` — what `send` uses with no recipient — is a chat room or a topic.

## Messages, the chatter and the texter

A channel turns a notification into a message: `ChatMessage(subject)`,
`SmsMessage(phone, subject, from_="")`, `PushMessage(subject, content)`. Messages are frozen;
`with_transport(...)`, `with_options(...)` and friends return copies. Provider options — blocks,
buttons, a parse mode — are a frozen `MessageOptions(kind, recipient_id, values)` that a
provider's builder renders, so a message survives a trip through a bus.

When the code has a message rather than a notification, send it directly:

```python
from xtr_notifier import Chatter, Texter

await Chatter(chat).send(ChatMessage("Deployed 4.1.0", transport="ops"))
await Texter(texts).send(SmsMessage("+3312345678", "Your code is 4812"))
```

Given a message bus, the chatter, the texter and the channels queue instead of sending, and
return `None`; `xtr_notifier.messenger.MessageHandler(transport)` sends what the bus hands back.

## Transports and DSNs

`Transport(factories, discovery)` builds transports from DSNs: one DSN gives one transport,
`a || b` a `FailoverTransport` (sticks to the first that works), `a && b` a
`RoundRobinTransport` (takes turns). A transport that raises `TransportError` is skipped for 60
seconds. `from_strings({...})` gives `Transports`, which sends a message through the transport
it names, or the first that supports it.

A DSN is `scheme://user:password@host:port/path?option=value`; `host` is `default` for the
provider's own API host. A factory serves a scheme: the ones given first, then those installed
libraries advertise in the group the builder reads — the chatter's
(`xtr_notifier.chatter_transport_factories`) or the texter's
(`xtr_notifier.texter_transport_factories`). A scheme nothing serves raises
`UnsupportedSchemeError`, naming the library to install when it is a known one.

## Providers

Each provider is a library of its own, installed beside this one; its factory is found by its
DSN scheme with no wiring. This package ships one transport, `null`, in both groups.

| Library | Scheme | Kind | DSN |
|---|---|---|---|
| xtr-notifier | `null` | chat, SMS, push | `null://null` |
| xtr-telegram-notifier | `telegram` | chat | `telegram://BOT_ID:TOKEN@default?channel=CHAT_ID` |
| xtr-slack-notifier | `slack` | chat | `slack://TOKEN@default?channel=CHANNEL` |

Writing one is a package with an `AbstractTransport`, an `AbstractTransportFactory` and an entry
point; the agent skill's `references/bridges.md` walks through it.

## Testing

Record what was sent with a `NotificationLoggerListener` (the bundle registers one when the
event dispatcher is active) and assert on it:

```python
from xtr_notifier.testing import assert_notification_count, assert_notification_subject_contains

assert_notification_count(listener.events, 1, "ops")
assert_notification_subject_contains(listener.events.get_messages()[0], "Disk")
```

A provider library checks its transport and factory with `TransportCases` /
`assert_transport_cases` and `FactoryCases` / `assert_factory_cases`, which report every case
that fails at once. None of it imports a test framework.

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what
removing it undoes.

- **Install** — `uv add "xtr-notifier[messenger]"`, or `uv add xtr-notifier` to send in-process
  only. Each provider is a library of its own (see [Providers](#providers)). It works with
  [xtr-http-client](../xtr-http-client), which providers are reached through,
  [xtr-event-dispatcher](../xtr-event-dispatcher), which announces every message and records
  them for tests, and [xtr-messenger](../xtr-messenger), which queues them — each used when
  installed.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Activate*, *Configure* and
  *Environment* steps below: it lists `NotifierBundle`, writes a starting
  `<app>/config/notifier.py` with one chat and one SMS-and-push transport, and
  `NOTIFIER_CHATTER_DSN` and `NOTIFIER_TEXTER_DSN`, both `null://null`, in `.env`. There is no
  ignore line to write. It prints the steps to install a provider and to route the messages to
  a worker, which a recipe cannot make for you.
- **Activate** — `NotifierBundle: {"all": True}` in `BUNDLES` in `<app>/bundles.py`, imported
  from `xtr_notifier.bundle`.
- **Brings along** — the HTTP client, messenger and event dispatcher bundles, each when its
  package is installed.
- **Configure** — the zero-config notifier has no channel and refuses every notification with
  `The "chat" channel does not exist.`; transports, the channel policy and the administrators go
  in `<app>/config/notifier.py`, a `@configure` function returning `NotifierConfig` — see
  [Kernel / bundle](#kernel--bundle). To queue messages, route `ChatMessage`, `SmsMessage` and
  `PushMessage` in `<app>/config/messenger.py`.
- **Environment** — `NOTIFIER_CHATTER_DSN` and `NOTIFIER_TEXTER_DSN`, the DSNs the written
  configuration reads when a message is first sent. A provider's DSN carries its token.
- **Ignore** — nothing.
- **Remove** — drop the `BUNDLES` entry, delete `<app>/config/notifier.py` and the two variables,
  then `uv remove xtr-notifier`.
- **Check** — `debug:bundles` shows `notifier` as `listed` and `active`; `debug:config notifier`
  shows the transports, the channel policy and the administrators.

## Kernel / bundle

```python
# app/config/notifier.py
from xtr_dependency_injection import configure, env
from xtr_notifier.bundle import AdminRecipientConfig, NotifierConfig


@configure
def notifier() -> NotifierConfig:
    return NotifierConfig(
        chatter_transports={"slack": env("SLACK_DSN"), "ops": "telegram://... || slack://..."},
        texter_transports={"sms": env("SMS_DSN")},
        channel_policy={"urgent": ["sms", "chat/slack"], "high": ["chat/slack"]},
        admin_recipients=[AdminRecipientConfig("ops@example.com", "+3312345678")],
        notification_on_failed_messages=True,
    )
```

| Field | Default | What it does |
|---|---|---|
| `chatter_transports` | `{}` | Chat transports by name; any brings the `chat` channel and `ChatterInterface` |
| `texter_transports` | `{}` | SMS and push transports; any brings the `sms` and `push` channels and `TexterInterface` |
| `channel_policy` | `{}` | Channels by importance value, for a notification naming none |
| `admin_recipients` | `()` | Who the application's own failures are reported to (`email` required) |
| `notification_on_failed_messages` | `False` | Report a message the bus gave up on to the administrators |
| `http_client` | `None` | Qualifier of the HTTP client providers are reached through |

What the bundle registers:

- `NotifierInterface` / `AdminRecipientsProviderInterface` — always.
- A `Transport` builder and `Transports` per kind, under the qualifiers `chatter` and `texter`,
  plus the chatter, the texter and the channels — only for a kind with transports. Nothing reads
  a DSN before a message is sent, so a DSN given through `env()` is checked where it is used.
- With the messenger bundle: a message whose type the bus routes (by class, by its wire name, or
  `*`) is queued, and a handler sends it through the same transports; an unrouted one is sent at
  once. The texter queues only when both SMS and push messages are routed.
- With the event dispatcher bundle: a `NotificationLoggerListener`, and every message announced.
- `notification_on_failed_messages=True` without the messenger or the event dispatcher bundle
  fails the build with `LogicError`.

Extension points, for an application or another bundle:

- Any class deriving from `TransportFactoryInterface` the application registers serves both
  kinds; tag one `CHATTER_TRANSPORT_FACTORY_TAG` or `TEXTER_TRANSPORT_FACTORY_TAG` to serve one.
  A factory keeping `AbstractTransportFactory`'s constructor is handed the HTTP client and the
  event dispatcher; one with a constructor of its own is built by the container.
- Tag a `ChannelInterface` service `CHANNEL_TAG` with `channel="<name>"` to add a channel.

## Errors

Every error derives from `NotifierError`.

| Error | Raised when |
|---|---|
| `InvalidArgumentError` | A DSN cannot be read, an option is not a boolean, a transport name is unknown |
| `IncompleteDsnError` | A DSN lacks a part its provider needs — a token, a user |
| `MissingRequiredOptionError` | A DSN lacks a required option |
| `UnsupportedSchemeError` | No factory serves a DSN's scheme |
| `LogicError` | A channel does not exist or cannot reach the recipient; no transport supports a message |
| `UnsupportedMessageTypeError` | A transport is handed a message of another kind |
| `UnsupportedOptionsError` | A transport is handed another provider's options |
| `MultipleExclusiveOptionsUsedError` | Options a provider takes only one of were set together |
| `LengthError` | A value is longer than the provider accepts |
| `TransportError` | A provider could not be reached or refused a message (carries the response) |
| `NotifierRuntimeError` | Every transport of a failover or round robin failed |

## Development

```sh
cd packages/xtr-notifier
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
