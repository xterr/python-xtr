---
name: xtr-mailer
description: How to send email with xtr-mailer — a DSN picks the transport (SMTP, sendmail, null or a provider's API), the mailer sends in-process or queues on a message bus, and listeners add the envelope, default headers, tracking, DKIM and S/MIME signing. Use when code must send an email, choose or write a mailer DSN, set up failover or round-robin transports, queue mail for a worker, force the envelope or recipients of a deployment, sign or encrypt outgoing mail, cap a transport with a rate limiter, add MailerBundle to an application on xtr-dependency-injection, write a provider library, or assert on sent mail in a test.
---

# xtr-mailer

A DSN names the transport; `MailerInterface` sends through whichever one it named. The email
itself is an xtr-mime `Email` — build it with the `xtr-mime` skill; this package only delivers
it.

## Quick reference

- Build a transport from a DSN: `Transport.from_dsn("smtp://user:pass@mail.example.com:587")`,
  or `Transport.from_dsns({"main": ..., "marketing": ...})` for several picked by an
  `X-Transport` header.
- Send: `mailer = Mailer(transport)` then `await mailer.send(email)` — returns nothing. The
  transport's own `await transport.send(email)` answers a `SentMessage`, or `None` when a
  listener rejected the email.
- Queue: `Mailer(transport, bus)` dispatches `SendEmailMessage` instead of sending. In an
  application that happens as soon as the messenger bundle is active and the message is routed.
- Envelope: read from the headers, or `Envelope(Address("bounces@example.com"), [Address(...)])`
  passed to `send`.
- Group: `failover(a b)` sticks to the first, `roundrobin(a b)` takes turns, both taking
  `?retry_period=<seconds>` after the `)`.
- Schemes here: `null`, `smtp`, `smtps`, `sendmail`, `sendmail+smtp`, `native`. A provider's
  comes from its own library — [references/providers.md](references/providers.md).
- Listeners, from `xtr_mailer.event_listener`, each with its own `PRIORITY`: `MessageListener`,
  `MessengerTransportListener`, `SmimeSignedMessageListener`, `SmimeEncryptedMessageListener`,
  `DkimSignedMessageListener`, `EnvelopeListener`, `MessageLoggerListener`.
- Headers, from `xtr_mailer.header`: `TagHeader`, `MetadataHeader`, `TrackingHeader`.
- Tests: `xtr_mailer.testing` — `assert_email_count`, `assert_queued_email_count`,
  `FactoryCases`.
- Errors derive from `MailerError` — and read
  [references/limitations.md](references/limitations.md) before trusting a DSN or a queue.

## Send an email

```python
from xtr_mailer import Mailer, Transport
from xtr_mime import Address, Email

email = (
    Email()
    .from_(Address("shop@example.com", "Example Shop"))
    .to("ana@example.com")
    .subject("Your order has shipped")
    .text("Your order is on its way.")
)

transport = Transport.from_dsn("null://null")
await Mailer(transport).send(email)
```

**Always write the port on an `smtp://` DSN.** With none it reaches 465 under implicit TLS for
every host but the literal `localhost` — `smtp://127.0.0.1` included.

## Send from a worker

```python
from xtr_mailer.messenger import MessageHandler, SendEmailMessage
from xtr_messenger import HandleMessageMiddleware, HandlersLocator, MessageBus

handlers = HandlersLocator()
handlers.register(SendEmailMessage, MessageHandler(transport))

await Mailer(transport, MessageBus([HandleMessageMiddleware(handlers)])).send(email)
```

The listeners run again in the worker, so signatures and headers are made where the mail goes. A
`TransportError` a handler raised reaches the caller unchanged. Attach bytes or a `File`, never a
stream that cannot seek back, to an email that is queued and also signed or encrypted.

## Shape every email with listeners

```python
from xtr_event_dispatcher import EventDispatcher
from xtr_mailer.event import MessageEvent
from xtr_mailer.event_listener import EnvelopeListener, MessageLoggerListener

dispatcher = EventDispatcher()
recorder = MessageLoggerListener()
for listener in (
    recorder,
    EnvelopeListener(
        "bounces@example.com",
        recipients=["staging@example.com"],
        allowed_recipients=[r"[^@]+@example\.com"],
    ),
):
    dispatcher.add_listener(MessageEvent, listener.on_message, priority=listener.PRIORITY)

transport = Transport.from_dsn("null://null", event_dispatcher=dispatcher)
sent = await transport.send(email)
assert sent.get_envelope().get_sender().get_address() == "bounces@example.com"
assert [r.get_address() for r in sent.get_envelope().get_recipients()] == [
    "staging@example.com",
    "ana@example.com",
]
```

`allowed_recipients` are Python regular expressions matched against a whole address, and they
only matter beside `recipients`: they keep the email's own envelope recipients that match, after
the ones given. With no `recipients`, nothing is filtered. Register a listener at its own
`PRIORITY`; higher runs earlier, and DKIM signs last.

## Testing

- Build real transports. `null://null` accepts, renders and discards, so it catches an email
  that cannot be sent; for SMTP run a server in the test rather than mocking the protocol.
- Record with a `MessageLoggerListener` on a real `EventDispatcher`, then assert:

  ```python
  from xtr_mailer.testing import assert_email_count, assert_queued_email_count

  assert_email_count(recorder.get_events(), 1)
  assert_email_count(recorder.get_events(), 1, "null://")
  assert_queued_email_count(recorder.get_events(), 0)
  ```

- Hold a provider's factory to the common contract with `FactoryCases` and
  `assert_factory_cases` — [references/providers.md](references/providers.md).
- Build an email per send: `Transports` consumes the `X-Transport` header on a successful send,
  so the same object sent twice goes to the default the second time.
- With a kernel, `assert_zero_config(MailerBundle)` is the bundle's contract test.

## Use in an application

`uv run xtr-recipes recipes:sync` applies the recipe shipped with this package: it lists
`MailerBundle`, writes `<app>/config/packages/mailer.py` with one transport read from the
environment, and `MAILER_DSN` in `.env`. There is no ignore line to write.

1. **Install** — `uv add xtr-mailer`; add `dkim` or `smime` for signing and encryption. The xtr
   packages it works with are not extras — install xtr-messenger, xtr-event-dispatcher,
   xtr-rate-limiter, xtr-console, xtr-logging or xtr-http-client and each is used when present.
2. **Activate** — `MailerBundle: {"all": True}` in `BUNDLES` in `<app>/config/bundles.py`,
   imported from `xtr_mailer.bundle`.
3. **Brings along** — the event dispatcher, messenger, HTTP client, rate limiter, logging and
   console bundles, each when installed, none required to send.
4. **Configure** — `MailerConfig` in a `<app>/config/packages/mailer.py` `@configure` function;
   with none, every email goes to `null://null`. Everything a listener does — `envelope`,
   `headers`, `tracking`, `dkim_signer`, `smime_signer`, `smime_encrypter` — needs
   xtr-event-dispatcher, and says so at build otherwise —
   [references/application.md](references/application.md).
5. **Environment** — `MAILER_DSN`, read when the mailer or the transport is first resolved.
   **Ignore** — nothing.
6. **Use** — inject `MailerInterface`. To send from a worker, route
   `xtr_mailer.messenger.SendEmailMessage` in `<app>/config/packages/messenger.py`; there is no
   configuration switch for it.
7. **Check** — `debug:bundles` shows `mailer` as `listed` and `active`; `debug:config mailer`
   shows what it resolved, never the DSN; `mailer:test <address>` sends one email.
8. **Remove** — `uv run xtr-recipes recipes:remove xtr-mailer`, which also deletes
   `<app>/config/packages/mailer.py` and the variable.

## Errors

| Error | Raised when |
| --- | --- |
| `MailerError` | Base of them all |
| `MailerRuntimeError` | The world failed while sending — no recipient has an S/MIME certificate, a default header cannot be set. Also `RuntimeError` |
| `LogicError` | Misuse — no transport, raw bytes with no envelope, a remote template on a transport that cannot render one, an extra missing, a rate limiter named but not configured. Also `RuntimeError` |
| `InvalidArgumentError` | A value cannot be used — a DSN, an option, an allow-list pattern, an unknown transport name. Also `ValueError` |
| `IncompleteDsnError` | A DSN leaves out the user or password its scheme needs. An `InvalidArgumentError` |
| `TransportError` | The mail could not be handed over. Carries `code` and a credential-free `debug`. What failover and round-robin move on from. A `MailerRuntimeError` |
| `UnexpectedResponseError` | An SMTP server answered with a code the exchange disallows. A `TransportError` |
| `HttpTransportError` | A provider's API refused the email; carries the `response`. A `TransportError` |
| `UnsupportedSchemeError` | No installed factory serves the scheme; it names the library to install. A `LogicError` |

An email the queue cannot carry is refused outside this hierarchy: the serializer reads every
queued email back, so `mailer.send` raises xtr-messenger's `MessageEncodingFailedError` naming
the limit or the class, and a tampered message in the worker a `MessageDecodingFailedError`.

## Do not

- Do not write an `smtp://` DSN without a port: it reaches 465 under TLS for every host but
  `localhost`, `127.0.0.1` included.
- Do not expect shell syntax in a sendmail `command`: it is run without a shell, so `$VAR`, `~`,
  `*` and `|` mean nothing.
- Do not leave a transport unstopped. Its socket, and a `-bs` sendmail child, stay until `stop()`
  — the bundle does it when the container closes.
- Do not queue an email carrying a non-seekable stream, an application subclass of `Email`, a
  header or a part of your own, or megabytes of attachments — the bytes travel on the broker.
- Do not add a `message_bus` option looking for the queue switch: route `SendEmailMessage`.
- Do not assume `Bcc` stays hidden under S/MIME encryption: every recipient certificate's issuer
  and serial is listed in clear.
- Do not rely on `encrypt` or `skip` to protect anyone — `encrypt` sends unreadable mail,
  `skip` leaves the address in `To` or `Cc`.
- Do not normalise an address before a certificate lookup and expect a match, or vary its case
  or its domain's form — the lookup is exact.
- Do not reuse one `Email` object for two sends through `Transports`.
- Do not assert on rendered bytes of a whole email: dates, ids and boundaries change every
  render.
- Do not register `Transports` or a transport yourself beside the bundle; configure
  `MailerConfig`.
