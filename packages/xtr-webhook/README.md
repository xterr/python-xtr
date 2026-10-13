<div align="center">

# xtr-webhook

**Receive webhooks — verified, replay-bounded, turned into events — and send them signed, in the legacy or the Standard Webhooks format.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="asyncio" src="https://img.shields.io/badge/asyncio-native-1f6feb">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

A webhook is an HTTP request from someone who is not a user, so the usual answers do not
apply: there is no session to trust, the body is the only thing signed, and a request captured
once can be sent again tomorrow. Handling one well means checking it against the right
secret, refusing anything outside a window, and getting off the request as fast as possible.

Sending one is the same problem from the other side: sign the exact bytes, say when they were
signed, and retry what the receiver refused.

This package does both ends, and turns what arrives into an
[xtr-remote-event](../xtr-remote-event) event, so the code that handles it never sees HTTP.

## Install

```sh
uv add xtr-webhook              # signatures, parsers, the endpoint, the events a webhook becomes
uv add "xtr-webhook[client]"    # + sending signed webhooks
uv add "xtr-webhook[di]"        # + the bundle
```

## Quick start

Receiving, with nothing but this package and a bus that handles in process. A controller is
given the parser for each type, the secret each is checked against, and where to hand on what it
read:

```python
import asyncio
import hmac

from xtr_http_message import Response, ServerRequest
from xtr_messenger import HandlersLocator, MessageBusConfig, MessageBusFactory, TransportConfig
from xtr_remote_event.messenger import ConsumeRemoteEventMessage
from xtr_webhook.client import RequestParser
from xtr_webhook.controller import WebhookController

SECRET = "the-secret"
BODY = b'{"total": 4200}'


async def consume(message: ConsumeRemoteEventMessage) -> None:
    event = message.event
    print(f"consumed {event.name} {event.id} {event.payload}")


async def main() -> None:
    handlers = HandlersLocator()
    _ = handlers.register(ConsumeRemoteEventMessage, consume)
    bus = MessageBusFactory(
        MessageBusConfig(
            transports={"sync": TransportConfig("sync://")},
            routing={ConsumeRemoteEventMessage: "sync"},
        ),
        handlers=handlers,
    ).bus()

    controller = WebhookController({"acme": RequestParser()}, {"acme": SECRET}, bus)

    signed = hmac.new(SECRET.encode(), b"order.paid" + b"evt_1" + BODY, "sha256").hexdigest()
    arrived = ServerRequest(
        "POST",
        "/webhook/acme",
        {
            "Content-Type": "application/json",
            "Webhook-Event": "order.paid",
            "Webhook-Id": "evt_1",
            "Webhook-Signature": f"sha256={signed}",
        },
        BODY,
    )

    answer = await controller.index_action("acme", arrived, Response())
    print(f"answered {answer.get_status_code()}")


asyncio.run(main())
```

```
consumed order.paid evt_1 {'total': 4200}
answered 202
```

In an application the endpoint and the controller are the bundle's — see
[Use in an application](#use-in-an-application).

## Receiving

`setup(app, kernel)` adds the endpoint — no `include_router` of your own:

```python
from fastapi import FastAPI
from xtr_dependency_injection import Kernel
from xtr_http_kernel import setup

app = FastAPI()
setup(app, Kernel("app"))
```

That serves `POST /webhook/{type}`, contributed as the route resource `webhook`. A routes file in
`<app>/config/routes/` — `routes.import_("webhook").prefix("/hooks")` — moves it to
`/hooks/webhook/{type}`, for an application keeping everything a stranger may call under one
path. Whichever it is, build the
URL you hand a sender from the route's name, `"webhook"` — a sender that was told a URL keeps
sending to it long after the deploy that changed the path.

One endpoint serves every sender. The `type` segment tells them apart: it picks the parser that
reads the webhook and the secret it is checked against, both configuration, so a new sender
needs no new route.

```python
# app/config/webhook.py
from xtr_dependency_injection import configure, env

from xtr_webhook.bundle import RouteConfig, WebhookConfig


@configure
def webhook() -> WebhookConfig:
    return WebhookConfig(
        routing={
            "acme": RouteConfig(secret=env("WEBHOOK_SECRET")),
            "stripe": RouteConfig(parser=StripeRequestParser, secret=env("STRIPE_SECRET")),
        },
    )
```

Pass a secret through `env(...)`, never as a literal: a placeholder is read only when the
endpoint is built, and no container report prints it.

Routing keys are kept verbatim, dashes included. A type nothing is routed to is answered `404`
with `No webhook parser found for the type given in the URL.` — from the sender's side that URL
does not exist.

### What the endpoint answers

| Answer | When |
|---|---|
| `202` | the webhook was read, and every event it carried is on the bus |
| `404` | nothing is routed to that type |
| `406` | the parser refused it: a signature that does not match, a timestamp outside the window, a body that will not decode, a request the matcher does not claim |
| whatever the refusal carries | a parser raising `RejectWebhookError` with its own status and headers |
| `5xx` | something behind the endpoint failed — a bus with nothing to handle the event above all |

The answer goes out before the events are handled, which is the point: a sender waiting on a
handler is a sender that times out and sends the webhook again. The refusal body is plain text
naming the check that refused, never the values that failed it.

A `5xx` is deliberate rather than tidied away. The sender then sends the webhook again, which is
the only outcome that does not lose what it carried.

### Writing a parser

One parser speaks for one sender. Subclass `AbstractRequestParser` and fill in the two things
that differ per sender — which requests are that sender's, and how to check and read one:

```python
from xtr_http_message_contracts import ServerRequestInterface
from xtr_remote_event import RemoteEvent

from xtr_webhook.client import (
    AbstractRequestParser,
    ChainRequestMatcher,
    IsJsonRequestMatcher,
    MethodRequestMatcher,
    RequestMatcherInterface,
)
from xtr_webhook.exception import RejectWebhookError


class AcmeRequestParser(AbstractRequestParser):
    def get_request_matcher(self) -> RequestMatcherInterface:
        return ChainRequestMatcher([MethodRequestMatcher("POST"), IsJsonRequestMatcher()])

    async def do_parse(self, request: ServerRequestInterface, secret: str) -> RemoteEvent:
        if request.get_header_line("X-Acme-Token") != secret:
            raise RejectWebhookError(406, "Signature is wrong.")
        payload = self.read_json(request)
        return RemoteEvent("acme", str(payload["id"]), payload)
```

The base class does what every parser would otherwise write again, and get wrong in the same
way: the shape check runs before the body is touched, a body that will not decode comes back as
a `406` rather than as a `500`, and the two answers are the ones the sender's side waits for.

- `self.read_body(request)` returns every byte of the body from its first one, rewinding the
  stream where it can — a signature covers exactly the bytes that arrived.
- `self.read_json(request)` decodes the body as a JSON object. An array or a bare value is
  refused; bytes that are not JSON at all raise, and `parse()` turns that into the same `406`.
- `do_parse` returns one event, a sequence of them, or `None` for a webhook to accept and
  ignore — a keep-alive, an event kind this parser does not speak for. `None` and an empty
  sequence are both answered as unparsable rather than accepted and dropped.
- Override `create_successful_response` for a sender that wants something of its own echoed
  back. The response is handed in and given back modified, because an HTTP message is immutable
  and the endpoint owns the response.
- Compare secrets with `hmac.compare_digest`, never `==`.

Matchers are small and compose: `MethodRequestMatcher("POST", "PUT")` (case-insensitive),
`IsJsonRequestMatcher()` (a media type of `application/json` or ending in `+json`, parameters
ignored), `ChainRequestMatcher([...])` (all must match).

### Signature formats

`RequestParser` is this library's own parser, the mirror of its sender, and reads either of two
signature schemes. `SignatureFormat` picks which a request must carry:

| Format | Signature header | Signed over | Event name in | Replay bounded |
|---|---|---|---|---|
| `SignatureFormat.LEGACY` | `sha256=<hex>` | event name + id + body | the `Webhook-Event` header | no |
| `SignatureFormat.STANDARD` | `v1,<base64>` | `<id>.<timestamp>.` + body | the payload's `type` key | yes |
| `SignatureFormat.TRANSITIONAL` | both, space separated | both of the above | both | for the Standard Webhooks entry |

The members *are* their strings, so a configuration carries `"standard"` and is understood with
no conversion step. Anything else is refused by `SignatureFormat.parse` with
`InvalidArgumentError`.

Both ends must have made the same choice, which is why the sender's configurators and the
receiver's parser each take it. `TRANSITIONAL` exists so they need not change on the same day: a
receiver accepts whichever scheme it already understands.

Under `STANDARD` the event name travels in the payload because that scheme's signature covers no
header at all — a name sent as one is a value the receiver cannot trust. A payload with no
`type` string names no event and is refused.

### Rotating a secret

The signature header may carry several whitespace-separated entries, one per secret in play, and
any one that verifies is enough. So a rotation is: the sender starts sending both signatures, the
receiver's secret is changed, the sender drops the old one. Each expectation is computed once
rather than per entry, and every comparison is `hmac.compare_digest`, so the time a refusal takes
says nothing about how much of it was right.

### The replay window

A delivery captured once can be sent again tomorrow, so a signed timestamp is held to a window
around now — `timestamp_tolerance`, 300 seconds by default. Zero or less turns the bound off, for
when clocks that cannot be kept close enough matter more than a replayed capture.

Plainly: **a `LEGACY` signature carries no timestamp, so the window protects only `STANDARD` and
`TRANSITIONAL`.** Under `LEGACY` the timestamp header is still sent, but nothing signs it, so
refusing on it would mean trusting a value an attacker sets. The check runs only after a Standard
Webhooks entry verified, which is when the timestamp is known to be the sender's. A timestamp
that does not read as an integer is refused too — a value that cannot be bounded is not accepted
on faith.

A request carrying both schemes is tried Standard-first, so it is replay-bounded whatever order
its entries arrive in.

### An empty secret

`RequestParser` raises `InvalidArgumentError` rather than refusing the request: an empty secret
is this side's configuration, not the sender's doing, so it surfaces as a `5xx`. A type with no
`secret` in its `RouteConfig` is checked against `""`, so set one in production — a parser of
your own that verifies nothing would otherwise accept every sender.

## Sending

Install `xtr-webhook[client]`. A webhook goes out as a message, so the delivery is not in the
request that caused it, and a refusal is retried by the bus:

```python
from xtr_remote_event import RemoteEvent

from xtr_webhook.messenger import SendWebhookMessage
from xtr_webhook.subscriber import Subscriber

_ = await bus.dispatch(
    SendWebhookMessage(
        Subscriber("https://example.com/hook", secret),
        RemoteEvent("order.paid", "evt_1", {"total": 4200}),
    )
)
```

A `Subscriber` is where the webhook goes and what signs it; the pair travels together because
neither is useful alone. Its `secret` is kept out of the `repr`, and an empty one is refused with
`InvalidArgumentError` — it would still sign, over the empty key, and send perfectly formed
webhooks no receiver can accept.

The message carries the subscriber whole rather than an id, because this library stores no
subscribers: the application knows where a webhook goes and says so once, here.

### What goes out

A webhook is built by a chain of configurators, each writing one part of the same
`OutgoingRequest`: `HeadersConfigurator` the headers naming the event, `JsonBodyConfigurator` the
payload as the body, `HeaderSignatureConfigurator` the signature over what the other two wrote.
It runs last, because it signs their output. They are separate because receivers disagree about
all three, so an unusual one means adding or replacing a step rather than the sender.

Under `LEGACY`, `RemoteEvent("order.paid", "evt_1", {"total": 4200})`:

```http
POST /hook HTTP/1.1
Content-Type: application/json
Webhook-Id: evt_1
Webhook-Timestamp: 1767225600
Webhook-Event: order.paid
Webhook-Signature: sha256=0f8c...

{"total":4200}
```

Under `STANDARD` the `Webhook-Event` header is not sent at all and the name is written into the
payload instead:

```http
POST /hook HTTP/1.1
Content-Type: application/json
Webhook-Id: evt_1
Webhook-Timestamp: 1767225600
Webhook-Signature: v1,dGhlLXNpZ25hdHVyZQ==

{"total":4200,"type":"order.paid"}
```

Under `TRANSITIONAL` both headers are sent and `Webhook-Signature` carries both entries, space
separated.

A payload that already says what it is keeps what it says: the application knows its own events
better than their source name does. The payload is copied before the key is added, so dispatching
a webhook never edits the dict the caller is still holding.

The body is written as compact JSON with nothing reordered — the bytes are the signed message, so
two runs over the same payload have to produce the same ones. A value JSON has no form for raises
`TypeError` from the serializer, unwrapped: what it refuses is its own vocabulary.

Header names and the legacy digest are all configurable:

| Option | Default |
|---|---|
| `event_header_name` | `"Webhook-Event"` |
| `id_header_name` | `"Webhook-Id"` |
| `timestamp_header_name` | `"Webhook-Timestamp"` |
| `signature_header_name` | `"Webhook-Signature"` |
| `signing_algorithm` | `"sha256"` |
| `signature_format` | `SignatureFormat.LEGACY` |
| `timestamp_tolerance` | `300` |

An algorithm this runtime cannot make is refused where it is configured, not at the first
delivery. The Standard Webhooks signature is always SHA-256; the scheme fixes it.

### Delivery errors and retries

Any answer outside 200-299 raises `DeliveryError`, carrying `.status_code` and `.url`. Nothing is
caught in the handler: the error is what makes the bus retry the delivery and, once the attempts
are spent, keep the message instead of dropping it. Swallowing it would turn every refused
webhook into one silently never sent. How many attempts, and how long between them, is the
messenger transport's — see [xtr-messenger](../xtr-messenger).

A redirect counts as refused. Redirects are never followed, whatever the client was built with:
following one would carry a signed body to an address nobody registered, and would hollow out the
guard below.

## Private network guard

**Opt-in, and off by default.** A subscriber URL is usually data — chosen by whoever registered
it — so without a guard a webhook is a way to ask this process to fetch an address only this
process can see: another service on the same network, an admin port, a cloud provider's metadata
endpoint handing out credentials.

```python
import httpx

from xtr_webhook.bridge.httpx import HttpxSender, NoPrivateNetworkTransport

client = httpx.AsyncClient(transport=NoPrivateNetworkTransport(httpx.AsyncHTTPTransport()))
sender = HttpxSender(client)
```

The check runs on what the host *resolves to*, not on how it is written, so neither a name
pointing inwards nor an address spelled unusually gets through. One refused address refuses the
whole delivery. The request is then pinned to the address that was checked, so a name whose
records change between the check and the connection — a rebinding attack — connects to what was
vetted or not at all; certificate verification still checks the original host name.

A refusal is `PrivateNetworkError`, carrying `.host` and `.address`. It is a `DeliveryError`, so
one `except` covers "it did not arrive" — though a retry will not arrive either, since nothing
about the network changes by trying again.

With no `subnets` it refuses every address that is not globally routable: loopback, private,
link-local, carrier-grade NAT, unique-local, multicast, reserved and unspecified alike. Give
`subnets` to replace that set, and `allow_list` to open one receiver without opening the network
it sits in. Both take IP networks or single addresses, never hostnames — the check runs on
resolved addresses, and a name could point anywhere by the time it is used.

In the bundle it is `no_private_network`, and it guards only the client the bundle builds:

```python
WebhookConfig(
    no_private_network=NoPrivateNetworkConfig(enabled=True, allow_list=("10.1.2.3",)),
)
```

Naming `subnets` or an `allow_list` while `enabled` is `False` is refused rather than silently
ignored — a configuration that looks like protection and is not. Combining the guard with
`http_client` is refused too: wrapping a client you registered would need the client library's
private internals and would still leave its own mounts unguarded. Leave `http_client` unset, or
build your client with `NoPrivateNetworkTransport` yourself.

## Testing your parsers

`xtr_webhook.testing` turns a directory of recorded payloads into tests. Install the helpers
with the `testing` extra first — they build requests with xtr-http-message:

```sh
uv add --dev "xtr-webhook[testing]"
```

Each `*.json` fixture has a sibling `*.py` defining a module-level `EXPECTED`, the event — or list
of events — it must parse to:

```python
from pathlib import Path

import pytest

from xtr_webhook.testing import ParserCase, assert_parses, parser_cases


@pytest.mark.anyio
@pytest.mark.parametrize(
    "case", parser_cases(Path(__file__).parent / "fixtures"), ids=lambda case: case.id
)
async def test_the_parser_reads_every_recorded_payload(case: ParserCase) -> None:
    await assert_parses(AcmeRequestParser(), case, secret="the-secret")
```

`parser_cases(fixtures_dir, extension="json")` walks the directory recursively and returns a
`ParserCase(id, payload, expected)` per fixture, sorted by id, so adding a sender's payload to
the directory adds a test. A fixture with no expectation file beside it raises
`InvalidArgumentError` naming both paths — a payload nobody wrote an expectation for is a test
that silently is not run.

`assert_parses(parser, case, *, secret="", headers=None, method="POST")` builds the request with
`Content-Type: application/json` plus whatever `headers` adds, parses it, and asserts the
events match. Pass the signature headers a real delivery carries through `headers`.

Nothing here imports pytest, so a fixture directory is usable from any runner.

## Security notes

- **Subscriber secrets travel inside the queued message body.** `SendWebhookMessage` carries the
  subscriber whole, so **the queue storage must be trusted**. The bus itself adds nothing to
  that: its logging middleware records the message type, the transport, the message id, the
  handler name and the stamps — never the body.
- **Receiving secrets belong in the environment**, passed as `env("...")`. A `RouteConfig`'s
  `secret` is kept out of its `repr`, and a placeholder is resolved only when the endpoint is
  built.
- **A `LEGACY` signature is not replay-bounded.** Use `STANDARD` where that matters.
- **An empty secret signs.** Both ends refuse one rather than send or accept webhooks nobody can
  verify.
- **Refusals say as little as the sender needs.** Name the check that refused, never the values
  that failed it.
- **Signatures are compared with `hmac.compare_digest`.** Do the same in a parser of your own.
- **Nothing follows a redirect**, so a signed body cannot be bounced to an address nobody
  registered.

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what
removing it undoes.

- **Install** — `uv add "xtr-webhook[client]"`; add `di` for the bundle. The endpoint that
  receives comes with the package; `client` is what sends (the HTTP client and the guard).
  Without `client`, no transport and no send handler are registered, and dispatching
  `SendWebhookMessage` fails with the bus's no-handler error.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Activate*, *Configure* and
  *Environment* steps below: it lists `WebhookBundle`, writes a starting
  `<app>/config/webhook.py` with one route, `<app>/config/routes/webhook.py` serving the
  endpoint at its default path, and `WEBHOOK_SECRET` (commented out) in `.env`. There is no
  ignore line to write. It prints the steps to call `setup` and to name your own types, neither
  of which a recipe can make for you.
- **Activate** — `WebhookBundle: {"all": True}` in `BUNDLES` in `<app>/bundles.py`, imported
  from `xtr_webhook.bundle`.
- **Brings along** — the remote-event bundle, the messenger bundle through it, and the HTTP
  kernel's bundle, always.
- **Configure** — needed to receive anything: with no routing the endpoint knows no type and
  answers every webhook `404`. Routing, header names, the signature format and the guard go in
  `<app>/config/webhook.py`, a `@configure` function returning `WebhookConfig` — see
  [Kernel / bundle](#kernel--bundle).
  `<app>/config/routes/webhook.py` imports the `webhook` route resource; move it under a prefix
  there.
- **Environment** — `WEBHOOK_SECRET`, the secret the written route verifies against, read when
  the endpoint is built; one per sender in practice.
- **Ignore** — nothing.
- **Load** — call `setup(app, kernel)` where the application is built; it adds the endpoint,
  `POST /webhook/{type}`.
- **Remove** — drop the `BUNDLES` entry, delete `<app>/config/webhook.py` and
  `<app>/config/routes/webhook.py`, then `uv remove xtr-webhook`.
- **Check** — `debug:bundles` shows `webhook` and `remote_event` as `listed` and `active`;
  `debug:config webhook` shows the resolved routing, header names and signature format.

## Kernel / bundle

```python
# app/bundles.py
from xtr_webhook.bundle import WebhookBundle

BUNDLES = {WebhookBundle: {"all": True}}
```

```python
# app/config/webhook.py
from xtr_dependency_injection import configure, env

from xtr_webhook.bundle import NoPrivateNetworkConfig, RouteConfig, WebhookConfig
from xtr_webhook.server import SignatureFormat


@configure
def webhook() -> WebhookConfig:
    return WebhookConfig(
        signature_format=SignatureFormat.STANDARD,
        timestamp_tolerance=300,
        no_private_network=NoPrivateNetworkConfig(enabled=True),
        routing={
            "acme": RouteConfig(secret=env("WEBHOOK_SECRET")),
            "stripe": RouteConfig(parser=StripeRequestParser, secret=env("STRIPE_SECRET")),
        },
    )
```

`WebhookConfig`:

| Field | Default | What it sets |
|---|---|---|
| `routing` | `{}` | what the endpoint does with each type, by the type in the URL |
| `signature_format` | `SignatureFormat.LEGACY` | the scheme both ends share; a string is accepted |
| `timestamp_tolerance` | `300` | seconds either side of now a signed timestamp may be; `0` turns the bound off |
| `signing_algorithm` | `"sha256"` | the digest the legacy signature is made with |
| `event_header_name` | `"Webhook-Event"` | where the event's name travels, where the scheme sends one |
| `id_header_name` | `"Webhook-Id"` | where the event's id travels |
| `timestamp_header_name` | `"Webhook-Timestamp"` | where the send time travels |
| `signature_header_name` | `"Webhook-Signature"` | where the signature entries travel |
| `http_client` | `None` | the qualifier of an `httpx.AsyncClient` you registered; `None` means the bundle builds and owns one |
| `no_private_network` | `NoPrivateNetworkConfig()` | whether the bundle-built client refuses to deliver inwards, and what counts as inwards |

`RouteConfig(parser=None, secret="")`: `parser` is the class reading that type's webhooks, built
by the container with its dependencies on the first webhook for it; `None` means the bundle's
own `RequestParser`, configured by the fields above. Two routes naming one class share one
instance.

The bundle registers the configurator chain, its own parser under the `webhook` qualifier — so
`Annotated[RequestParserInterface, Target("webhook")]` resolves to it — every custom parser the
routing names, the endpoint's route loader, and the controller behind it. The controller gets its parsers as a
service locator, so it never holds the container and a route's parser is built only when the
first webhook for it arrives.

The sending side is registered only when httpx is installed: the client (the bundle's own,
closed with the container, or the one `http_client` names), the sender over it, the transport,
and `SendWebhookHandler` with it. The handler is registered beside the transport it needs, so a
container never holds a handler it cannot build.

The zero-config path routes nothing, signs with the legacy scheme under the default header names,
and does no I/O at build or boot.

## Errors

Everything this library raises derives from `WebhookError`, and carries what went wrong as typed
attributes rather than forcing a message to be parsed. None of them repeats a secret.

| Error | Raised when | Carries |
|---|---|---|
| `InvalidArgumentError` | a value cannot be used — an unknown signature format, an empty secret, an unavailable algorithm; also a `ValueError` | — |
| `LogicError` | this library was used in a way that cannot work — a chain that wrote no body, a signer running before the timestamp; also a `RuntimeError` | — |
| `RejectWebhookError` | an incoming webhook is refused; it carries the answer the sender gets | `.status_code`, `.headers` |
| `WebhookRuntimeError` | something a webhook depends on failed while it was handled; also a `RuntimeError` | — |
| `DeliveryError` | a receiver answered an outgoing webhook outside 200-299 | `.status_code`, `.url` |
| `PrivateNetworkError` | a host an outgoing webhook named resolves into a refused network; a `DeliveryError` with `.status_code` `0` | `.host`, `.address` |

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-webhook`; run the commands below from there. The `python-xtr-webhook`
repository is a read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync --all-extras
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
