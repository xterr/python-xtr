<div align="center">

# xtr-mailer

**Send email through SMTP, sendmail or a provider's API — picked by DSN, in-process or queued on a message bus, with failover, round-robin, envelope and header overrides, DKIM and S/MIME signing, and S/MIME encryption.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="asyncio" src="https://img.shields.io/badge/asyncio-native-1f6feb">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

Sending email is rarely one call to one server. Development discards it, staging sends it to one
address, production hands it to a relay — or to a provider's API, and to a second one when the
first is down. Every deployment wants a different answer, and none of them is worth a code
change.

xtr-mailer puts the answer in a string. A DSN names the transport; `failover(...)` and
`roundrobin(...)` group several; the same `MailerInterface` sends through whichever one the
string picked. What every email carries — the envelope it is delivered with, default headers, a
DKIM signature, S/MIME signing and encryption — is set once, as configuration, and applied by
listeners rather than by the code that writes the mail.

- **One DSN, any transport.** `null://`, `smtp://` and `smtps://`, `sendmail://`, `native://`,
  and a provider's scheme as soon as its library is installed — found by the scheme, with no
  wiring.
- **Send now or queue.** With [xtr-messenger](../xtr-messenger) the email becomes a
  `SendEmailMessage` a worker sends; without it, the same call sends in-process.
- **Never one server.** `failover(a b)` sticks to the first until it fails; `roundrobin(a b)`
  takes turns. A failed transport rests, then rejoins.
- **Signing and encryption.** DKIM through [xtr-mime](../xtr-mime), S/MIME signing and
  encryption per recipient certificate.
- **Credentials stay in the DSN.** No error, string form, log line or container report quotes a
  password.

## Install

```sh
uv add xtr-mailer
```

| Extra | Brings | For |
|---|---|---|
| `dkim` | `xtr-mime[dkim]` (dkimpy, cryptography) | `DkimSignedMessageListener`, the `dkim_signer` configuration |
| `smime` | `xtr-mime[smime]` (cryptography) | `SmimeSignedMessageListener`, `SmimeEncryptedMessageListener`, the `smime_signer` and `smime_encrypter` configuration |

`uv add "xtr-mailer[dkim,smime]"` takes both. A provider's transports come from a library of its
own, installed as `uv add "xtr-mailer[<provider>]"` — see [Providers](#providers).

The xtr packages the mailer works with are **not** extras: install the ones the application
wants, and the bundle uses each when it is there. [xtr-messenger](../xtr-messenger) queues
emails, [xtr-rate-limiter](../xtr-rate-limiter) caps a transport,
[xtr-event-dispatcher](../xtr-event-dispatcher) carries the events listeners run on,
[xtr-console](../xtr-console) adds `mailer:test`, [xtr-logging](../xtr-logging) gives the
`mailer` channel somewhere to write, and [xtr-http-client](../xtr-http-client) is what a
provider's transports reach their API through.

## Quick start

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
mailer = Mailer(transport)

await mailer.send(email)
```

`Mailer.send` returns nothing: an email is accepted, or an error says why it was not. The
transport answers with more, for a test or a log:

```python
sent = await transport.send(email)

assert sent is not None
assert "Subject: Your order has shipped" in sent.to_string()
assert sent.get_message_id() != ""
```

A `SentMessage` holds what went on the wire, the `Message-ID` the email was given, the envelope
it was delivered with, and whatever the server said. `send` answers `None` only when a listener
rejected the email.

The envelope — who the server is told the mail is from, and who it is for — is read from the
headers. Give one explicitly to part the two, as a bounce address does:

```python
from xtr_mailer import Envelope

envelope = Envelope(Address("bounces@example.com"), [Address("ana@example.com")])

sent = await transport.send(email, envelope)

assert sent.get_envelope().get_sender().get_address() == "bounces@example.com"
```

The envelope sender must have an ASCII local part, and an envelope must name at least one
recipient. Recipient names are dropped: the server is given addresses.

### Send from a worker

With [xtr-messenger](../xtr-messenger), hand the mailer a bus and the email is queued as a
`SendEmailMessage` instead of sent:

```python
from xtr_mailer.messenger import MessageHandler, SendEmailMessage
from xtr_messenger import HandleMessageMiddleware, HandlersLocator, MessageBus

handlers = HandlersLocator()
handlers.register(SendEmailMessage, MessageHandler(transport))
mailer = Mailer(transport, MessageBus([HandleMessageMiddleware(handlers)]))

await mailer.send(email)
```

The listeners run again in the worker, so the signature and the headers are made where the mail
actually goes. A `TransportError` a handler raised reaches the caller as it is, so a synchronous
bus behaves like no bus at all.

### Fall back and take turns

```python
from xtr_mailer.transport import FailoverTransport

transport = Transport.from_dsn(
    "failover(smtp://mail.example.com:587 smtp://backup.example.com:587)?retry_period=15"
)

assert isinstance(transport, FailoverTransport)
assert str(transport) == "failover(smtp://mail.example.com:587 smtp://backup.example.com:587)"
```

`failover(...)` stays with the first transport until it raises a `TransportError`, then moves on;
`roundrobin(...)` takes the next one each send, starting somewhere random. A failed member rests
`retry_period` seconds — 60 by default — then rejoins. Groups nest:
`roundrobin(smtp://a failover(smtp://b smtp://c))`.

### Several named transports

```python
transports = Transport.from_dsns({"main": "null://null", "marketing": "null://null"})

email.get_headers().add_text_header("X-Transport", "marketing")

sent = await transports.send(email)
assert str(transports) == "[main,marketing]"
```

The first named transport sends every email that does not ask for another by `X-Transport`. The
header is removed before the mail goes out, and put back only if the send fails — see
[Known limitations](#known-limitations).

## DSN reference

A DSN is `scheme://[user[:password]@]host[:port][?options]`. The host is required; write
`default` where a transport has no use for one. Credentials and any option value holding a
space, `)` or `?` are percent-encoded. Unknown options are ignored.

| Scheme | Sends through | Host and port |
|---|---|---|
| `null` | nowhere: the email is accepted, rendered and discarded | ignored, `null://null` by convention |
| `smtp` | a mail server, plain or STARTTLS, or implicit TLS on 465 | the server; port as below |
| `smtps` | a mail server over implicit TLS | the server, port 465 by default |
| `sendmail` / `sendmail+smtp` | a local `sendmail` program | ignored, `sendmail://default` by convention |
| `native` | the host's own `sendmail`, found on `PATH` | ignored, `native://default` by convention |

**`smtp://` and `smtps://`.** The port decides the encryption when the DSN does not:

| DSN | Connects to | Encryption |
|---|---|---|
| `smtp://mail.example.com` | port 465 | implicit TLS |
| `smtp://localhost` | port 25 | plain, STARTTLS if offered |
| `smtp://mail.example.com:587` | port 587 | plain, STARTTLS if offered |
| `smtp://mail.example.com:465` | port 465 | implicit TLS |
| `smtp://mail.example.com?auto_tls=0` | port 25 | plain, no STARTTLS |
| `smtps://mail.example.com` | port 465 | implicit TLS |

Give the port. A `smtp://` DSN with none reaches 465 for every host but the literal
`localhost` — `127.0.0.1` included — which is rarely what a local relay wants; see
[Known limitations](#known-limitations).

| Option | Value | Default |
|---|---|---|
| `auto_tls` | boolean: use STARTTLS when the server offers it | on |
| `require_tls` | boolean: refuse to send without TLS | off |
| `verify_peer` | boolean: check the certificate and the name on it | on |
| `peer_fingerprint` | an MD5, SHA-1 or SHA-256 digest in hex, compared after connecting | none |
| `source_ip` | the local IPv4 or IPv6 address to connect from | the system's choice |
| `timeout` | seconds any one step of the exchange may take | 60 |
| `local_domain` | what the greeting names this host as | `[127.0.0.1]` |
| `max_per_second` | emails a second this transport starts; 0 is no pacing | 0 |
| `restart_threshold` | emails after which the session is reopened; 0 is never | 100 |
| `restart_threshold_sleep` | seconds to wait after closing the session, before the next email reopens it; ignored while `restart_threshold` is 0 | 0 |
| `ping_threshold` | seconds of silence after which the server is pinged | 100 |

A bad value is an `InvalidArgumentError` naming the option. The user and password are the SMTP
login; the transport tries CRAM-MD5, PLAIN, LOGIN and XOAUTH2, in that order, against what the
server offers.

**`sendmail://`.** The `command` option is the program and its arguments:

| DSN | Runs |
|---|---|
| `sendmail://default` | `/usr/sbin/sendmail -bs` — an SMTP session over the program's own streams |
| `sendmail://default?command=%2Fusr%2Fsbin%2Fsendmail%20-t` | `/usr/sbin/sendmail -i -f<sender> -- <recipients>` — the message piped in, the envelope's recipients named |

The command must hold `-bs` or `-t`. `-t` picks the piped mode and is then dropped: the envelope
names the recipients, after `--` so none is read as an option, rather than sendmail reading them
from the headers — which would also deliver to a `Bcc`. `-i` is added when neither `-i` nor `-oi`
is given, and `-f<sender>` unless the command sets `-f`. The command is **not** run through a
shell: it is split into words the way a shell splits them, quotes grouping a word that holds a
space — `-F "Example Shop"` is two arguments, the second with its space — and the words are
handed to the operating system as they are. So globbing, a pipeline and `$VAR` have no effect,
and the program is looked up as written. Not every `sendmail` implements `-bs`; see
[Known limitations](#known-limitations).

**`native://`.** `sendmail` on `PATH`, else `/usr/sbin/sendmail` when it is executable, run as
`-t -i`, one process per email. With neither, building the transport raises a `TransportError`
naming the `sendmail://default` and `smtp://...` DSNs to use instead.

**Groups.** `failover(` and `roundrobin(` are lowercase, their members separated by spaces,
nesting at most 32 deep, each group optionally followed by `?retry_period=<seconds>`. Garbage
anywhere is an `InvalidArgumentError`: `The mailer DSN has some garbage at the end.`

## Listeners

Every email passes a `MessageEvent` before it goes, and listeners shape it. Each carries the
`PRIORITY` it belongs at; higher runs earlier.

```python
from xtr_event_dispatcher import EventDispatcher
from xtr_mailer.event import MessageEvent
from xtr_mailer.event_listener import EnvelopeListener, MessageListener, MessageLoggerListener

dispatcher = EventDispatcher()
recorder = MessageLoggerListener()
for listener in (
    recorder,
    EnvelopeListener(
        "bounces@example.com",
        recipients=["staging@example.com"],
        allowed_recipients=[r"[^@]+@example\.com"],
    ),
    MessageListener(),
):
    dispatcher.add_listener(MessageEvent, listener.on_message, priority=listener.PRIORITY)

transport = Transport.from_dsn("null://null", event_dispatcher=dispatcher)
sent = await transport.send(email)

assert sent.get_envelope().get_sender().get_address() == "bounces@example.com"
assert [r.get_address() for r in sent.get_envelope().get_recipients()] == [
    "staging@example.com",
    "ana@example.com",
]
assert recorder.get_events().get_transports() == ["null://"]
```

| Listener | Priority | What it does |
|---|---|---|
| `MessageListener` | 0 | Adds the default headers, each by its rule — set-if-empty, add or replace — and renders the body with a `BodyRendererInterface` when given one |
| `MessengerTransportListener` | 0 | Turns an `X-Bus-Transport` header on a queued email into the messenger transports it is queued to |
| `SmimeSignedMessageListener` | -128 | Signs the email with S/MIME |
| `SmimeEncryptedMessageListener` | -200 | Encrypts an email marked `X-SMime-Encrypt` for its recipients' certificates |
| `DkimSignedMessageListener` | -228 | Signs the email with DKIM — last, so the signature covers what the others did |
| `EnvelopeListener` | -255 | Overrides the envelope sender and recipients, keeping those an allow-list pattern matches |
| `MessageLoggerListener` | -255 | Keeps every email it saw, for a test or a development report |

`EnvelopeListener`'s `allowed_recipients` matter only beside `recipients`: the allow-list keeps
the email's own envelope recipients that match, after the ones given, and with no `recipients`
nothing is filtered at all — a listener given a sender and an allow-list changes the sender and
leaves every recipient where it was. The patterns are Python regular expressions, each matched
against a whole address: `r"[^@]+@example\.com"` passes `ana@example.com` and refuses
`ana@example.com.example.org`.

In an application these are registered, at these priorities, by the bundle from configuration —
see [Kernel / bundle](#kernel--bundle).

### Provider-neutral headers

```python
from xtr_mailer.header import MetadataHeader, TagHeader, TrackingHeader

headers = email.get_headers()
headers.add(TagHeader("welcome"))
headers.add(MetadataHeader("order", "A-17"))
headers.add(TrackingHeader(opens=True, clicks=False))

wire = email.to_string()
assert "X-Tag: welcome" in wire
assert "X-Metadata-order: A-17" in wire
assert "X-Track: opens=true; clicks=false" in wire
```

`X-Tag`, `X-Metadata-<key>` and `X-Track` say what every provider has a name of its own for; a
provider's transport translates them, and a mail server passes them through as ordinary headers.
`None` in a `TrackingHeader` leaves the provider's default alone.

## mailer:test

With [xtr-console](../xtr-console) installed, the bundle adds a command that sends one email
through the configured transport, straight to it — never through the bus:

```sh
<script> mailer:test ana@example.com
<script> mailer:test ana@example.com --from shop@example.com --subject Hello --body "Hello Ana"
<script> mailer:test ana@example.com --transport marketing
```

It prints nothing when the email went, and `[ERROR] <what failed>` on the error stream
otherwise, exiting non-zero. `--transport` names one of several configured transports.

## Testing

`xtr_mailer.testing` checks what was sent, and holds a transport factory to what every factory
owes. It imports no test framework.

```python
from xtr_mailer.testing import assert_email_count, assert_queued_email_count

events = recorder.get_events()

assert_email_count(events, 1)
assert_email_count(events, 1, "null://")
assert_queued_email_count(events, 0)
```

`assert_email_is_queued` and `assert_email_is_not_queued` ask the same of one event. A
`MessageLoggerListener` is where the events come from — in an application the bundle registers
one whenever the kernel is in debug.

Build real transports: `null://null` accepts and discards, and renders the email on the way, so
it catches an email that cannot be sent. For SMTP, run a server in the test rather than mocking
the protocol.

A provider library's factory is held to the common contract with `FactoryCases`:

```python
from xtr_mailer import Dsn
from xtr_mailer.testing import FactoryCases, assert_factory_cases
from xtr_mailer.transport import NullTransport, NullTransportFactory

assert_factory_cases(
    FactoryCases(
        create_factory=NullTransportFactory,
        supports=[(Dsn("null", "null"), True), (Dsn("smtp", "example.com"), False)],
        create=[(Dsn("null", "null"), NullTransport())],
        unsupported_scheme=[(Dsn("smtp", "example.com"), None)],
    )
)
```

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what
removing it undoes.

- **Install** — `uv add xtr-mailer`, or `uv add "xtr-mailer[dkim,smime]"` for signing and
  encryption. Add [xtr-messenger](../xtr-messenger) to queue emails, and
  [xtr-event-dispatcher](../xtr-event-dispatcher), [xtr-rate-limiter](../xtr-rate-limiter),
  [xtr-console](../xtr-console), [xtr-logging](../xtr-logging) and
  [xtr-http-client](../xtr-http-client) for what each brings — every one is used when
  installed, and none is an extra of this package.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Activate*, *Configure* and
  *Environment* steps below: it lists `MailerBundle`, writes a starting
  `<app>/config/packages/mailer.py` with one transport read from the environment, and
  `MAILER_DSN`, `null://null`, in `.env`. There is no ignore line to write. It prints the two
  steps a recipe cannot make for you: pointing `MAILER_DSN` at a real server, and routing
  `SendEmailMessage` to a worker.
- **Activate** — `MailerBundle: {"all": True}` in `BUNDLES` in `<app>/config/bundles.py`,
  imported from `xtr_mailer.bundle`.
- **Brings along** — the event dispatcher, messenger, HTTP client, rate limiter, logging and
  console bundles, each when its package is installed, and none of them required to send. The
  mime bundle is not among them: the mailer uses the xtr-mime library, not its container
  services.
- **Configure** — optional: with no configuration every email goes to `null://null`, which
  accepts and discards it. The transport, the envelope every email is delivered with, default
  headers, tracking and signing go in `<app>/config/packages/mailer.py`, a `@configure` function
  returning `MailerConfig` — see [Kernel / bundle](#kernel--bundle). Everything a listener does —
  `envelope`, `headers`, `tracking`, `dkim_signer`, `smime_signer`, `smime_encrypter` — needs
  [xtr-event-dispatcher](../xtr-event-dispatcher) installed, and says so at build otherwise. To
  send from a worker, route `xtr_mailer.messenger.SendEmailMessage` in
  `<app>/config/packages/messenger.py`; there is no switch for it here.
- **Environment** — `MAILER_DSN`, the DSN the written configuration reads when the mailer or the
  transport is first resolved, not when the application boots. It carries the mail server's
  password, which no container report shows.
- **Ignore** — nothing: an email is sent, never written to disk.
- **Remove** — drop the `BUNDLES` entry, delete `<app>/config/packages/mailer.py` and the
  variable (`uv run xtr-recipes recipes:remove xtr-mailer` does all three), then
  `uv remove xtr-mailer`.
- **Check** — `debug:bundles` shows `mailer` as `listed` and `active`; `debug:config mailer`
  shows the envelope, headers, tracking and signing it resolved — never the DSN;
  `mailer:test <address>` sends one email through it.

## Kernel / bundle

With xtr-dependency-injection in the application, list the bundle:

```python
# app/config/bundles.py
from xtr_mailer.bundle import MailerBundle

BUNDLES = {MailerBundle: {"all": True}}
```

It registers:

| Service | Under | Built |
|---|---|---|
| `Mailer` | `MailerInterface` | when first asked for |
| `Transports` | `TransportInterface` | with the mailer, which takes it: the DSN is read then, and the sessions are closed when the container does |
| `MessageLoggerListener` | itself | in debug only, and only with the event dispatcher bundle |
| `MailerTestCommand` | `mailer:test` | with the console bundle |
| `SendEmailMessageHandler` | the handler of `SendEmailMessage` | with the messenger bundle |

Nothing is built at boot. The DSN is read when the mailer or the transport is first asked for —
the mailer takes the transports, so resolving either resolves both — and a DSN that does not
parse, a scheme no factory serves and a rate limiter named but not configured are refused there,
before any email. No socket is opened and no key file read until an email is sent.

```python
# app/services/order_mail.py
from xtr_dependency_injection import as_service
from xtr_mailer import MailerInterface
from xtr_mime import Email


@as_service
class OrderMail:
    def __init__(self, mailer: MailerInterface) -> None:
        self.mailer = mailer

    async def shipped(self, address: str) -> None:
        await self.mailer.send(
            Email()
            .from_("shop@example.com")
            .to(address)
            .subject("Your order has shipped")
            .text("Your order is on its way.")
        )
```

| `MailerConfig` field | Default | What it does |
|---|---|---|
| `dsn` | `None` | The one transport every email goes through. Cannot be given with `transports` |
| `transports` | `{}` | Transports by name, a DSN or a `TransportConfig` each; the first sends unless `X-Transport` names another |
| `envelope` | `EnvelopeConfig()` | The sender and recipients to override, and the allow-list keeping an email's own recipients beside the ones given — which does nothing without `recipients` |
| `headers` | `{}` | Headers every email carries, a string or a list of strings each |
| `tracking` | `TrackingConfig()` | Open and click tracking, as an `X-Track` header |
| `dkim_signer` | `None` | The key, domain and selector to sign with. Needs the `dkim` extra |
| `smime_signer` | `None` | The certificate and key to sign with. Needs the `smime` extra |
| `smime_encrypter` | `None` | Where recipients' certificates are found. Needs the `smime` extra |
| `http_client` | `None` | Which HTTP client a provider's transports reach their API through |

With neither `dsn` nor `transports`, the mailer sends to `null://null`. Both together is an
`InvalidArgumentError`: `"dsn" and "transports" cannot be used together.`

Every field but `dsn`, `transports` and `http_client` is applied by a listener, so each needs the
[xtr-event-dispatcher](../xtr-event-dispatcher) bundle; configured without it, the build is
refused naming the option: `The "envelope" option needs the "event_dispatcher" bundle; install
xtr-event-dispatcher beside xtr-mailer.` The signing fields also need their extra —
`The "dkim" extra is required to use DKIM: uv add "xtr-mailer[dkim]".`

```python
# app/config/packages/mailer.py
from xtr_dependency_injection import configure, env
from xtr_mailer.bundle import EnvelopeConfig, MailerConfig, TrackingConfig, TransportConfig


@configure
def mailer() -> MailerConfig:
    return MailerConfig(
        transports={
            "main": TransportConfig(env("MAILER_DSN"), rate_limiter="mail"),
            "marketing": TransportConfig(env("MAILER_MARKETING_DSN")),
        },
        envelope=EnvelopeConfig(
            sender="bounces@example.com",
            recipients=["staging@example.com"],
            allowed_recipients=[r"[^@]+@example\.com"],
        ),
        headers={"X-Campaign": "spring", "Reply-To": ["support@example.com"]},
        tracking=TrackingConfig(opens=True, clicks=True),
    )
```

**Rate limiting.** `TransportConfig(dsn, rate_limiter="mail")` names a limiter the
[xtr-rate-limiter](../xtr-rate-limiter) bundle configures; an email over the limit raises
`RateLimitExceededError`. Without that bundle the build is refused, naming the limiter. A
`failover(...)` or `roundrobin(...)` group takes none, and neither does it take `max_per_second`:
an option after a group's `)` is read as `retry_period` alone, so anything else is an
`InvalidArgumentError` — `The mailer DSN has some garbage at the end.` Pace each member's own
DSN with `max_per_second` instead, or cap a single transport with `rate_limiter`.

**Signing and encryption.**

```python
# app/config/packages/mailer.py
from xtr_dependency_injection import configure, env
from xtr_mailer.bundle import (
    DkimSignerConfig,
    MailerConfig,
    SmimeEncrypterConfig,
    SmimeSignerConfig,
)


@configure
def mailer() -> MailerConfig:
    return MailerConfig(
        dsn=env("MAILER_DSN"),
        dkim_signer=DkimSignerConfig(
            key="file://var/dkim/example.pem", domain="example.com", select="mail"
        ),
        smime_signer=SmimeSignerConfig(certificate="var/smime/shop.crt", key="var/smime/shop.key"),
        smime_encrypter=SmimeEncrypterConfig(
            certificates={"ana@example.com": "var/smime/ana.crt"},
            on_missing_certificate="fail",
        ),
    )
```

`DkimSignerConfig` also takes `passphrase`, `header_canon` and `body_canon` (`"simple"` or
`"relaxed"`), `headers_to_ignore` and `body_show_length`. `SmimeEncrypterConfig` takes either
`certificates` — a mapping the bundle turns into an `InMemorySmimeCertificateRepository` — or
`repository`, a `Reference` to one of yours implementing `SmimeCertificateRepositoryInterface`,
never both; plus `cipher` (`"aes-256-cbc"` by default, or `"aes-128-cbc"`), `encrypt_for_sender`,
and `on_missing_certificate`:

| `on_missing_certificate` | A recipient with no certificate |
|---|---|
| `fail` (default) | The email is refused, naming them. Nothing is logged |
| `encrypt` | They are logged, and still sent the email — which they cannot read |
| `skip` | They are logged and dropped from the envelope, so the mail never reaches them |

Only an email carrying an `X-SMime-Encrypt` header is encrypted; the header is neither sent nor
encrypted.

**Logging.** With the [xtr-logging](../xtr-logging) bundle the mailer writes to a `mailer`
channel the bundle adds. No line says an email was sent or failed: what is written is the
transport's own doings, at debug — an SMTP session starting, started, stopping and stopped, a
sendmail run starting and stopped, a wait `max_per_second` imposed and the one after a session
closed at its `restart_threshold` — plus, at error, each member of a `failover(...)` or
`roundrobin(...)` group that failed, and, at warning, the recipients an encrypted email had no
certificate for. Read a `MessageLoggerListener` for what was sent. Without that bundle nothing
is logged and nothing complains.

**A provider's transports.** Installing a provider library is enough: its factory is found by
the DSN's scheme. A factory needing more than the discovery hands it is registered by its own
bundle under `MAILER_TRANSPORT_FACTORY_TAG` (`"mailer.transport_factory"`), and tagged factories
are asked before the installed ones.

## Errors

Every error derives from `MailerError`, importable from `xtr_mailer` and `xtr_mailer.exception`.

| Error | Raised when |
|---|---|
| `MailerError` | The base: catch it to catch them all |
| `MailerRuntimeError` | Something outside the code failed while sending — no recipient has an S/MIME certificate, a default header cannot be set. Also a `RuntimeError` |
| `LogicError` | The library was used in a way that cannot work — a `Transports` with no transport, raw bytes with no envelope, a remote-template email on a transport that cannot render one, an extra not installed, a rate limiter named but not configured. Also a `RuntimeError` |
| `InvalidArgumentError` | A value cannot be used — a DSN that does not parse, an option value of the wrong shape, a bad allow-list pattern, a transport name that does not exist. Also a `ValueError` |
| `IncompleteDsnError` | A DSN leaves out a part its scheme needs, such as the user or password a provider's factory requires. An `InvalidArgumentError` |
| `TransportError` | The mail could not be handed over — no connection, a refused recipient, a sendmail process that failed. Carries `code` and a `debug` transcript that never holds a credential. What `failover(...)` and `roundrobin(...)` move on from. A `MailerRuntimeError` |
| `UnexpectedResponseError` | An SMTP server answered with a code the exchange does not allow; `code` is that reply code. A `TransportError` |
| `HttpTransportError` | A provider's API answered with a status saying the email was not accepted; carries the `response`. A `TransportError` |
| `UnsupportedSchemeError` | No installed factory serves a DSN's scheme: `The "acme" scheme is not supported.` A `mailgun` scheme — the one provider this package knows of — names the extra instead: `Unable to send emails via "mailgun" as the bridge is not installed. Try running: uv add "xtr-mailer[mailgun]".` A `LogicError` |

An email the queue cannot carry is the one refusal that is not a `MailerError`: the serializer
reads every queued email back before handing it over, so `mailer.send` raises
[xtr-messenger](../xtr-messenger)'s `MessageEncodingFailedError`, naming the limit or the class
— see [Known limitations](#known-limitations).

## Providers

A provider's transports live in a library of its own, installed beside this one; its factory is
found by its DSN scheme with no wiring, and `uv add "xtr-mailer[<provider>]"` brings it along.
This package ships the transports that need no provider:

| Library | Scheme | Sends through | DSN |
|---|---|---|---|
| xtr-mailer | `null` | nowhere | `null://null` |
| xtr-mailer | `smtp`, `smtps` | a mail server | `smtp://USER:PASSWORD@mail.example.com:587` |
| xtr-mailer | `sendmail`, `sendmail+smtp` | a local sendmail | `sendmail://default` |
| xtr-mailer | `native` | the host's own sendmail | `native://default` |

No provider library is published yet, and this package carries no `xtr-mailer[<provider>]` extra
to install: a provider scheme raises `UnsupportedSchemeError`, which names the extra for a
`mailgun` scheme — the one provider it knows of — and the scheme alone for any other. Writing a
provider library is a package with an `AbstractApiTransport` or `AbstractHttpTransport`, an
`AbstractTransportFactory` and an entry point; the agent skill's
[references/providers.md](src/xtr_mailer/.agents/skills/xtr-mailer/references/providers.md)
walks through it.

## Known limitations

- **An `smtp://` DSN with no port reaches 465, under implicit TLS.** Every host but the literal
  `localhost` — `127.0.0.1`, `[::1]` and `LOCALHOST` included — so `smtp://127.0.0.1` tries TLS
  on 465 rather than plain SMTP on 25. Write the port.
- **A sendmail command is not run through a shell.** The program and its arguments are split on
  spaces, honouring quotes, and handed to the operating system: no `$VAR`, `~`, `*`, `|`, `&&`
  or redirection has any effect, and the program is looked up as written. Put a shell in the
  command itself if you need one.
- **`sendmail://default` needs a `sendmail` that speaks `-bs`.** It opens an SMTP session over
  the program's own streams, which OpenSMTPD's `sendmail` does not implement — and probably not
  msmtp's. Use `?command=/usr/sbin/sendmail%20-t`, or `native://default`, where it does not.
- **The sendmail timeout is not a DSN option.** A child process gets 60 seconds, for the whole
  run in `-t` mode and for each reply in `-bs` mode. Only `SendmailTransport.set_timeout()`
  changes it, so a DSN-built transport keeps the 60.
- **A finished `-bs` session keeps its child until the transport is stopped.** The program stays
  running, holding the session, until `stop()` or the end of the event loop; `-t` mode waits for
  its child on every email instead.
- **A transport dropped without `stop()` keeps its socket.** Nothing closes it on garbage
  collection: the connection stays open until the server drops it or the process ends. Call
  `stop()`, or let the bundle do it — it closes the transports when the container closes.
- **A stalled SMTP server holds shutdown up to the timeout.** `stop()` sends `QUIT` and waits for
  the reply, and it waits for a send already in flight, each step of which may take the full
  `timeout` — 60 seconds by default. Several transports are stopped one after another, so their
  waits add up. Lower `timeout` where shutdown must be quick.
- **Queued emails are bounded, and the bound bites where the email is written.** What the broker
  hands a worker is untrusted, and folding a forged header is costly, so an email read from the
  queue is held to: per message or part, 512 headers, 64 KiB of header text, 8 KiB per value,
  1000 entries in an address or id list and 64 header parameters; per email, 2048 headers,
  192 KiB of header text, 2000 addresses (Bcc counted), 16 KiB of display-name text, 1024
  non-ASCII name words, 16 KiB of non-ASCII text per value and 32 KiB per email, 256 parts, 100
  attachments, and parts nested 32 deep. Each piece of an email carries its own bound too: a
  file name and a content type at most 256 characters, a header name 1 to 256 printable ASCII
  characters, a display name 256, a charset and a language 64, an address 320, and a remote
  template's variables plain JSON — a tuple or a set among them is refused. A real email stays
  far under every one. The limits are read limits, but the serializer reads every email back
  before handing it over, so an oversized one never reaches the broker: `mailer.send` raises
  [xtr-messenger](../xtr-messenger)'s `MessageEncodingFailedError`, naming where the email went
  over — `message.headers.fields holds more than 512 headers.` — never what it held. A message
  tampered with on the broker is refused in the worker the same way, with a
  `MessageDecodingFailedError`. Neither is a `MailerError`.
- **A path or stream attachment travels as content.** An email queued carries its attachments'
  bytes, not their paths, so the worker needs no access to the file — and a 10 MB attachment is
  10 MB on the broker. A stream that cannot seek back is read once: attached to an email that is
  also signed or encrypted and queued, it reaches the server empty, because the signing or
  encrypting listener read it first. Attach bytes or a `File` to an email you sign, encrypt and
  queue.
- **An envelope read from the headers is fixed when the email is queued.** Queue an email with no
  explicit envelope and the addresses its `To`, `Cc` and `Bcc` held at that moment travel with
  it; a listener in the worker changing those headers does not change where the mail goes.
- **The queue carries this library's own classes only.** An application subclass of `Email`, of a
  header or of a part is refused as the email is written, naming the class: `mailer.send` raises
  `MessageEncodingFailedError` and its reason is `An email of class "MyEmail" cannot be queued.`
  Carry your own data in headers, or send in-process.
- **`X-Bus-Transport` reaches the mail server.** It is removed from the copy the event carries,
  not from the email that is queued: the worker reads it off the queue and renders it, header and
  all, so an SMTP server is given it too — as it is for an email that is not routed to the bus
  and so sent in-process. The email the caller holds keeps it either way. A server passes it on
  and ignores it; remove it yourself where that matters.
- **An email is queued only when `SendEmailMessage` is routed.** There is no switch in this
  package's configuration: with the messenger bundle active and
  `xtr_mailer.messenger.SendEmailMessage` routed — by its class, one of its bases, or `"*"` — the
  mailer queues; otherwise it sends in-process. A route under its wire name is not a route, and
  an email is never dropped for want of one.
- **Re-sending one `Email` object through `Transports` goes to the default.** `X-Transport` is
  removed before the send and put back only when it fails, so the same object sent twice reaches
  the named transport once and the first configured one after that. Build an email per send.
- **S/MIME encryption shows who every recipient is.** The encrypted message lists each recipient
  certificate's issuer and serial number in clear, so a `Bcc` identity is visible to the `To` and
  `Cc` recipients and to every relay. Send `Bcc` copies as their own emails where that matters.
- **`skip` drops a recipient from the envelope, not from the headers.** An address with no
  certificate stops receiving the mail, but still appears in `To` or `Cc` for everyone who does.
- **`encrypt` sends mail nobody without a certificate can read.** They receive a message not
  encrypted for them. It is logged, and sent anyway.
- **A certificate is found by the exact address.** The lookup does no normalisation at all:
  letter case counts, Unicode is compared code point by code point, and an international domain
  is found only in the form the mapping holds. Hold each address as the emails write it.
- **Certificate files are read on the event loop, once per email.** An encrypted send reads every
  recipient's certificate from disk while the loop waits. Keep them local, and few.
- **An email is rendered whole in memory.** It takes about its rendered size while it is sent,
  attachments included — see [xtr-mime](../xtr-mime)'s own limitations.
- **A header folder in CPython 3.14.0 can loop forever.** Its standard-library folder, which
  xtr-mime calls for header values holding no encoded word, does not terminate on some
  whitespace-heavy subjects. Run a current 3.14 patch release.
- **`EnvelopeListener` and `MessageLoggerListener` share a priority.** Both sit at -255, so which
  of them runs first is not defined: a recorded email may show the envelope either before or
  after the override. It matters to a test reading the recorder, never to the mail sent.

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-mailer`; run the commands below from there. The `python-xtr-mailer` repository is
a read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
