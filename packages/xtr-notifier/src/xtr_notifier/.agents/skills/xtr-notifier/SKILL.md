---
name: xtr-notifier
description: How to send notifications with xtr-notifier — a notification sent to chat, SMS and push channels picked by the notification or by an importance policy, through provider transports configured by DSN, with failover and round robin, sent in-process or queued through xtr-messenger. Use when an application must alert a chat room or a phone, send an SMS code or a push message, configure a provider by DSN, fall over between providers, route notifications by importance, report failed queued messages to administrators, assert in a test what was notified, add NotifierBundle to an application, or write a provider library (a transport and its factory) for the notifier.
---

# xtr-notifier

A notification says what happened and how much it matters; the notifier picks its channels and
each channel sends a message through a transport chosen by a DSN. Providers are libraries of
their own, found by their DSN scheme.

## Quick reference

- Notify — `await notifier.send(Notification(subject, content=..., importance=...,
  channels=["chat/slack", "sms"]), *recipients)`; no recipients means `NoRecipient()`.
- Channels — `ChatChannel`, `SmsChannel` (needs a recipient with a `phone`), `PushChannel`, each
  built with a transport or a `message_bus=`. `"chat/slack"` sends on `chat` through `slack`.
- Policy — `ChannelPolicy({"urgent": ["sms", "chat"]})` picks channels when a notification names
  none; `Importance` is a `StrEnum` (`urgent`, `high`, `medium`, `low`).
- Direct — `Chatter(transport).send(ChatMessage(...))`, `Texter(transport).send(SmsMessage(...))`;
  with a bus they queue and return `None`.
- Transports — `Transport(factories, discovery).from_string("a || b")` (failover) or
  `"a && b"` (round robin); `from_strings({...})` gives named `Transports`.
- Discovery — `TransportFactoryDiscovery(TransportFactoryDiscovery.CHATTER_GROUP |
  TEXTER_GROUP, http_client=..., event_dispatcher=...)`; `null://null` is built in.
- Messages are frozen: `with_transport`, `with_options`, `with_subject` return copies.
- Bus — `xtr_notifier.messenger.MessageHandler(transport)`; importing `xtr_notifier.messenger`
  declares the messages' wire names.
- Every error derives from `NotifierError`.

## Send a notification

```python
from xtr_notifier import Notifier, Transport
from xtr_notifier.channel import ChannelPolicy, ChatChannel
from xtr_notifier.notification import Importance, Notification
from xtr_notifier.transport import TransportFactoryDiscovery

discovery = TransportFactoryDiscovery(TransportFactoryDiscovery.CHATTER_GROUP)
chat = Transport(discovery=discovery).from_strings({"ops": "null://null"})
notifier = Notifier({"chat": ChatChannel(chat)}, ChannelPolicy({"urgent": ["chat/ops"]}))

await notifier.send(Notification("Disk almost full", importance=Importance.URGENT))
```

Report an error with `Notification.from_exception(error, channels=["chat"])`; read an importance
from a log level with `Notification.importance_from_level("error")`.

## Render a channel's message yourself

Implement `as_chat_message` (or `as_sms_message`, `as_push_message`) on a `Notification`
subclass; return `None` to fall back to the default message:

```python
from xtr_notifier.message import ChatMessage, MessageOptions
from xtr_notifier.notification import Notification


class Deployed(Notification):
    def as_chat_message(self, recipient, transport_name):
        return ChatMessage(self.subject, MessageOptions("slack", "deploys", {"unfurl": False}))
```

`MessageOptions(kind, recipient_id, values)` holds JSON data only; a provider sends options
only when `kind` is its own.

## Configure providers by DSN

A DSN is `scheme://user:password@host?options`; `host` is `default` for the provider's own API.
Install the provider library (`uv add xtr-telegram-notifier`) and its scheme is served. A scheme
nothing serves raises `UnsupportedSchemeError` naming the library to install.

## Write a provider library

See [references/bridges.md](references/bridges.md): an `AbstractTransport`, an
`AbstractTransportFactory`, one entry point per scheme, and the `xtr_notifier.testing` cases.

## Testing

```python
from xtr_notifier.event_listener import NotificationLoggerListener
from xtr_notifier.testing import (
    assert_notification_count,
    assert_notification_subject_contains,
    assert_queued_notification_count,
)

listener = NotificationLoggerListener()  # listen to MessageEvent with on_notification
assert_notification_count(listener.events, 1, "ops")
assert_queued_notification_count(listener.events, 0)
assert_notification_subject_contains(listener.events.get_messages()[0], "Disk")
```

Use `null://null` to send nowhere; under the bundle a `NotificationLoggerListener` is registered
when the event dispatcher bundle is active — get it from the container.

## Use in an application

`uv run xtr-recipes recipes:sync` applies the recipe shipped with this package: it lists
`NotifierBundle`, writes `<app>/config/packages/notifier.py`, and `NOTIFIER_CHATTER_DSN` and
`NOTIFIER_TEXTER_DSN` (both `null://null`) in `.env`. It prints the steps it cannot make.

1. **Install** — `uv add "xtr-notifier[messenger]"` (or `xtr-notifier` alone); a provider
   library per provider. xtr-http-client, xtr-event-dispatcher and xtr-messenger are used when
   installed.
2. **Activate** — `NotifierBundle: {"all": True}` in `BUNDLES` in `<app>/config/bundles.py`
   (`from xtr_notifier.bundle import NotifierBundle`).
3. **Brings along** — the HTTP client, messenger and event dispatcher bundles, each when its
   package is installed.
4. **Configure** — `<app>/config/packages/notifier.py`, a `@configure` function returning
   `NotifierConfig`: `chatter_transports`, `texter_transports`, `channel_policy`,
   `admin_recipients` (`AdminRecipientConfig`), `notification_on_failed_messages`, `http_client`.
   With no transports there is no channel: sending raises `The "chat" channel does not exist.`
5. **Queue** — route `ChatMessage`, `SmsMessage`, `PushMessage` in `<app>/config/packages/messenger.py`;
   an unrouted message is sent at once.
6. **Environment** — `NOTIFIER_CHATTER_DSN`, `NOTIFIER_TEXTER_DSN`. **Ignore** — nothing.
7. **Use** — inject `NotifierInterface`, `ChatterInterface` or `TexterInterface`.
8. **Extend** — tag a factory `CHATTER_TRANSPORT_FACTORY_TAG` / `TEXTER_TRANSPORT_FACTORY_TAG`,
   or a channel `CHANNEL_TAG` with `channel="<name>"`.
9. **Check** — `debug:bundles` shows `notifier` active; `debug:config notifier`.
10. **Remove** — drop the `BUNDLES` entry, delete `<app>/config/packages/notifier.py` and the two
    variables, then `uv remove xtr-notifier`.

## Errors

| Error | When |
|---|---|
| `LogicError` | No channel can be determined, a channel does not exist or cannot reach the recipient, no transport supports the message, failed-message reporting without its peer bundles |
| `InvalidArgumentError` | Unreadable DSN, non-boolean option, unknown transport name, policy without the importance |
| `IncompleteDsnError` / `MissingRequiredOptionError` | A DSN lacks a token or a required option |
| `UnsupportedSchemeError` | No factory serves the scheme |
| `UnsupportedMessageTypeError` | A transport got a message of another kind |
| `TransportError` | The provider was unreachable or refused; the one error failover moves on from |
| `NotifierRuntimeError` | Every transport of a failover or round robin failed |

## Do not

- Do not write a DSN with a token into code or configuration; read it with `env("...")`.
- Do not mutate a message; use its `with_*` copies.
- Do not put objects in `MessageOptions.values` — JSON data only, or the message will not cross
  the bus.
- Do not create an HTTP client inside a transport; it takes the application's.
- Do not catch `TransportError` inside a transport to retry; failover and the bus do that.
