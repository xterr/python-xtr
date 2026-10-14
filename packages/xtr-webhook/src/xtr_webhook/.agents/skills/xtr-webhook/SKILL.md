---
name: xtr-webhook
description: How to receive and send webhooks with xtr-webhook — verify an incoming request against a subscriber secret, bound it to a replay window, turn it into a remote event, and send signed webhooks through a message bus in the legacy or the Standard Webhooks format. Use when an application must accept a provider callback, verify an HMAC signature header, mount a webhook endpoint, write a parser for one sender, rotate a signing secret, choose between the legacy and Standard Webhooks signature, send signed webhooks to subscribers with retries, stop an outgoing request from reaching a private address or cloud metadata endpoint, test a parser against recorded payloads, or add WebhookBundle to an application.
---

# xtr-webhook

A webhook is an HTTP request from someone who is not a user, so there is no session to trust,
the body is the only thing signed, and a request captured once can be sent again tomorrow. This
package verifies one, bounds it to a window, and turns it into an
[xtr-remote-event](https://github.com/xterr/python-xtr) event so the code that handles it never
sees HTTP. Sending is the same problem from the other side.

## Quick reference

- Receive — `setup(app, kernel)` adds `POST /webhook/{type}` (route resource `webhook`, movable
  in `<app>/config/routes/webhook.py`); the type picks the parser and the secret.
  `WebhookController(parsers, secrets, bus)` is what answers.
- Parse — subclass `AbstractRequestParser` and fill in `get_request_matcher()` and
  `async do_parse(request, secret)`. `RequestParser` is the built-in one. The matchers are
  `xtr_http_foundation`'s, and `IsJsonRequestMatcher` reads the body rather than the
  `Content-Type` header.
- Send — `await bus.dispatch(SendWebhookMessage(Subscriber(url, secret), event))`. Needs the
  `client` extra, which brings xtr-http-client; `Transport` posts through any
  `HttpClientInterface`.
- Formats — `SignatureFormat.LEGACY` (default), `STANDARD`, `TRANSITIONAL`. Members are their
  strings. Only `STANDARD` signs the timestamp, so only it bounds replays.
- Guard — `NoPrivateNetworkConfig(enabled=True)` in the bundle, or
  `NoPrivateNetworkHttpClient(client)` by hand. Opt-in, off by default.
- Answers — `202` read, `404` unknown type, `406` refused, `5xx` something behind the endpoint
  failed.
- Test — `parser_cases`, `ParserCase`, `assert_parses` from `xtr_webhook.testing`.
- Every error derives from `WebhookError`.

## Receive a webhook

With `xtr-webhook[di]`, call `setup` — it adds the endpoint — and route each sender's type:

```python
from fastapi import FastAPI
from xtr_dependency_injection import Kernel
from xtr_http_kernel import setup

app = FastAPI()
setup(app, Kernel("app"))
```

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

- One endpoint serves every sender, so a new sender is configuration, not another route. Give
  each subscriber the URL its type is served at, built from the route's name `"webhook"`.
- `routes("/hooks")` moves the endpoint to `/hooks/webhook/{type}`.
- A route with no `parser` uses the bundle's own `RequestParser`, configured by the surrounding
  `WebhookConfig`. Two routes naming one parser class share one instance.
- Secrets go through `env(...)`. A placeholder is read only when the endpoint is built, and no
  container report prints it.
- The sender is answered before the events are handled — each event goes out as a
  `ConsumeRemoteEventMessage` on the bus — because a sender waiting on a handler times out and
  sends the webhook again.
- Routing keys are kept verbatim, dashes included.

Without the container, build the controller by hand over a mapping of parsers, a mapping of
secrets and a bus. See the package README's Quick start for a runnable one.

## Write a parser

One parser speaks for one sender:

```python
import hmac

from xtr_http_foundation import (
    ChainRequestMatcher,
    IsJsonRequestMatcher,
    MethodRequestMatcher,
    RequestMatcherInterface,
)
from xtr_http_message_contracts import ServerRequestInterface
from xtr_remote_event import RemoteEvent

from xtr_webhook.client import AbstractRequestParser
from xtr_webhook.exception import RejectWebhookError


class AcmeRequestParser(AbstractRequestParser):
    def get_request_matcher(self) -> RequestMatcherInterface:
        return ChainRequestMatcher([MethodRequestMatcher("POST"), IsJsonRequestMatcher()])

    async def do_parse(self, request: ServerRequestInterface, secret: str) -> RemoteEvent:
        body = await self.read_body(request)
        expected = hmac.new(secret.encode(), body, "sha256").hexdigest()
        if not hmac.compare_digest(expected, request.get_header_line("X-Acme-Signature")):
            raise RejectWebhookError(406, "Signature is wrong.")
        payload = await self.read_json(request)
        return RemoteEvent("acme", str(payload["id"]), payload)
```

The base class already does what every parser would otherwise rewrite: the matcher runs before
anything is read out of the request, a body that will not decode comes back as a `406` rather
than a `500`, and both answers are the ones the sender's side waits for.

- `await self.read_body(request)` returns every byte from the first one, rewinding the stream
  where it can — a signature covers exactly what arrived. Reading a body is awaited.
- `await self.read_json(request)` decodes a JSON object. An array or a bare value is refused;
  bytes that are not JSON raise, and `parse()` turns that into the same `406`.
- Return one event, a sequence, or `None` for a webhook to accept and ignore. `None` and an
  empty sequence are answered as unparsable, not accepted.
- `RejectWebhookError(status_code=406, message="", headers=None)` carries the whole answer. The
  message reaches the sender as plain text, so name the check that refused and nothing more.
- Override `create_successful_response` — an `async def`, so it can write a body — for a sender
  that wants something echoed back; `create_rejected_response` is its counterpart for a refusal.
  The response is handed in and given back modified; an HTTP message is immutable.
- Matchers come from `xtr_http_foundation`, not from this package: `MethodRequestMatcher(["POST",
  "PUT"])` (one method or a sequence), `IsJsonRequestMatcher()`, `ChainRequestMatcher([...])`
  (all must match), plus matchers over the path, host, port, scheme, a header, a query parameter
  and the address it came from. `matches()` is awaited, so a rule may be about the body.
- `IsJsonRequestMatcher` reads the body, not the `Content-Type` header: a JSON body carrying no
  header is claimed, and an `application/json` request whose body is not JSON is refused with
  `Request does not match.` before the parser sees it.

## Send a webhook

With `xtr-webhook[client]` installed:

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

- `Subscriber(url, secret)` is frozen and keeps the secret out of its `repr`. An empty secret
  raises `InvalidArgumentError` — it would still sign, over the empty key.
- The chain is `HeadersConfigurator` → `JsonBodyConfigurator` → `HeaderSignatureConfigurator`,
  and the signer runs last because it signs the other two's output. Replace or add a step for a
  receiver that disagrees.
- `Transport(client, headers, body, signer)` posts through any `HttpClientInterface` — the
  bundle's choice is the client `WebhookConfig.http_client` names, the default one when unset.
  It asks for no redirect and passes no timeout: a delivery's timeout is the client's
  (`default_options.timeout`, or a scoped client of its own).
- Any answer outside 200-299 raises `DeliveryError`. Nothing is caught, so the bus retries and,
  once the attempts are spent, keeps the message. A redirect counts as refused and is never
  followed. A delivery nothing answered raises the client's own `TransportError`, retried alike.
- Without the `client` extra no transport and no send handler are registered, and the dispatch
  fails with the bus's no-handler error.
- The subscriber secret travels inside the queued message body, so the queue storage must be
  trusted. The bus logs the message type, transport, id, handler name and stamps, never the body.

## Choose a signature format

| Format | Header value | Signed over | Event name in | Replay bounded |
| --- | --- | --- | --- | --- |
| `LEGACY` | `sha256=<hex>` | name + id + body | the `Webhook-Event` header | no |
| `STANDARD` | `v1,<base64>` | `<id>.<timestamp>.` + body | the payload's `type` key | yes |
| `TRANSITIONAL` | both, space separated | both | both | for the Standard entry only |

- Both ends must have made the same choice. `TRANSITIONAL` is the migration window, so they need
  not change on the same day.
- `LEGACY` carries no signed timestamp, so `timestamp_tolerance` protects only `STANDARD` and
  `TRANSITIONAL`. Under `LEGACY` the timestamp header is sent but nothing signs it.
- Under `STANDARD` the `Webhook-Event` header is not sent at all; the name goes in the payload,
  because that scheme's signature covers no header.
- A rotation works because the signature header may carry several whitespace-separated entries
  and any one that verifies is enough.
- `SignatureFormat.parse("standard")` is the single door for a string; anything else raises
  `InvalidArgumentError`.

Depth — the exact bytes signed, the `whsec_` secret encoding, the rotation sequence and the
literal requests each format emits — is in
[references/signature-formats.md](references/signature-formats.md).

## Guard outbound requests

Opt-in, off by default. A subscriber URL is data, so without it a webhook is a way to make this
process fetch an address only this process can see.

In the bundle, around the client `http_client` names (the default one when unset):

```python
from xtr_webhook.bundle import NoPrivateNetworkConfig, WebhookConfig

WebhookConfig(no_private_network=NoPrivateNetworkConfig(enabled=True, allow_list=("10.1.2.3",)))
```

By hand, wrap the client the transport is given:

```python
from xtr_http_client import HttpClient, NoPrivateNetworkHttpClient

from xtr_webhook.server import (
    HeadersConfigurator,
    HeaderSignatureConfigurator,
    JsonBodyConfigurator,
    JsonPayloadSerializer,
    Transport,
)

transport = Transport(
    NoPrivateNetworkHttpClient(HttpClient.create()),
    HeadersConfigurator(),
    JsonBodyConfigurator(JsonPayloadSerializer()),
    HeaderSignatureConfigurator(),
)
```

- The check runs on what the host *resolves to*, and the request is then pinned to the address
  that was checked, so DNS rebinding connects to what was vetted or not at all.
- With no `subnets` it refuses the networks only this one can reach — loopback, private,
  link-local, carrier-grade NAT, unique-local, multicast, reserved, unspecified.
- `subnets` replaces that set; `allow_list` opens one receiver without opening its network. Both
  take IP networks or single addresses, never hostnames.
- A refusal is the client's `TransportError`, before anything is sent:
  `Host "<host>" is blocked for "<url>".` or `IP "<ip>" is blocked for "<url>".`. Retrying
  changes nothing.
- `subnets` or a non-empty `allow_list` with `enabled=False` is refused. Turning the guard on
  without xtr-http-client installed raises `LogicError` when the container is built.

## Testing

`xtr_webhook.testing` turns a directory of recorded payloads into tests. Before using it, install
the `testing` extra — the helpers build requests with xtr-http-message:
`uv add --dev "xtr-webhook[testing]"`.

Each `*.json` fixture has a sibling `*.py` defining a module-level `EXPECTED`, the event or list of
events it must parse to:

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

- `parser_cases(fixtures_dir, extension="json")` walks recursively and returns a
  `ParserCase(id, payload, expected)` per fixture, sorted by id, so dropping a payload in the
  directory adds a test. A fixture with no sibling raises `InvalidArgumentError` naming both
  paths.
- `assert_parses(parser, case, *, secret="", headers=None, method="POST")` builds the request
  with `Content-Type: application/json` plus `headers`, parses it, and asserts the events match.
  Pass the signature headers a real delivery carries through `headers`.
- Nothing there imports pytest, so the helpers work under any runner.
- For the whole endpoint, build a `WebhookController` over a mapping of parsers and a recording
  bus and call `index_action(type, request, Response())`; assert the status and what reached the
  bus.
- For the sending side, give `Transport` a `MockHttpClient` from xtr-http-client over a
  `MockResponse`, and read what was sent off the response: `get_request_url()`,
  `get_request_options()["headers"]` and `["body"]`. `MockResponse(info={"http_code": 500})`
  scripts a refusal. In an application, `HttpClientConfig(mock_response_factory=True)` makes the
  `MockHttpClient` service the transport; script it with `set_response_factory`.
- Freeze time by passing a `MockClock` as `clock` to `HeadersConfigurator` or `RequestParser`, so
  a timestamp and its window are decided rather than raced.

## Use in an application

`uv run xtr-recipes recipes:sync` applies the recipe shipped with this package: it lists
`WebhookBundle`, writes a starting `<app>/config/webhook.py` with one route,
`<app>/config/routes/webhook.py`, and `WEBHOOK_SECRET` (commented out) in `.env`. It prints the
steps it cannot make — calling `setup` and naming your own types.

1. **Install** — `uv add "xtr-webhook[client]"`; add `di` for the bundle. The endpoint comes
   with the package; `client` sends, bringing xtr-http-client and its bundle.
2. **Activate** — `WebhookBundle: {"all": True}` in `BUNDLES` in `<app>/bundles.py`
   (`from xtr_webhook.bundle import WebhookBundle`).
3. **Brings along** — the remote-event bundle, the messenger bundle through it, and the HTTP
   kernel's bundle, always; the HTTP client bundle when xtr-http-client is installed.
4. **Configure** — needed to receive anything: with no routing the endpoint knows no type and
   answers every webhook `404`. `<app>/config/webhook.py`, a `@configure` function returning
   `WebhookConfig` — `routing`, `signature_format`, `timestamp_tolerance`, `signing_algorithm`,
   the four header names, `http_client`, `no_private_network`. A delivery's timeout is set on
   the client, in `<app>/config/http_client.py`.
5. **Environment** — `WEBHOOK_SECRET`, the secret the written route verifies against, read when
   the endpoint is built; one per sender in practice. **Ignore** — nothing.
6. **Load** — call `setup(app, kernel)`; it adds `POST /webhook/{type}`, arranged by
   `<app>/config/routes/webhook.py` (`routes.import_("webhook").prefix("/hooks")` moves it).
7. **Use** — declare a consumer for each type with
   `@as_remote_event_consumer("<type>")`, and inject the bundle's parser where you need it with
   `Annotated[RequestParserInterface, Target("webhook")]`.
8. **Check** — `debug:bundles` shows `webhook` and `remote_event` as `listed` and `active`;
   `debug:config webhook` shows the resolved routing, header names and signature format.
9. **Remove** — drop the `BUNDLES` entry, delete `<app>/config/webhook.py` and
   `<app>/config/routes/webhook.py`, then `uv remove xtr-webhook`.

## Errors

Everything derives from `WebhookError` and carries typed attributes.

| Error | Raised when | Carries |
| --- | --- | --- |
| `InvalidArgumentError` | a value cannot be used — an unknown format, an empty secret, an unavailable algorithm; also a `ValueError` | — |
| `LogicError` | the library was used in a way that cannot work — a chain that wrote no body, a signer before the timestamp; also a `RuntimeError` | — |
| `RejectWebhookError` | an incoming webhook is refused; it carries the answer the sender gets | `.status_code`, `.headers` |
| `WebhookRuntimeError` | something a webhook depends on failed while it was handled | — |
| `DeliveryError` | a receiver answered outside 200-299 | `.status_code`, `.url` |

An `InvalidArgumentError` is configuration to fix, never an answer to a request. A
`RejectWebhookError` is the answer to a request and nothing else. A delivery nothing answered,
and one the private-network guard refused, raise the client's `TransportError`
(xtr-http-client-contracts) unwrapped.

## Do not

- Do not compare a signature with `==`. Use `hmac.compare_digest`, so the time a refusal takes
  says nothing about how much of it was right.
- Do not put the reason a check failed into a refusal message. Name the check; a sender is not
  debugged by its receiver.
- Do not read the body with anything but `read_body`/`read_json`, and do not re-encode a payload
  before verifying — the signature covers the bytes that arrived.
- Do not rely on `timestamp_tolerance` under `LEGACY`; that format signs no timestamp. Use
  `STANDARD` where replay protection matters.
- Do not trust the `Webhook-Event` header under `STANDARD`. That signature covers no header; the
  name is in the payload's `type`.
- Do not handle a webhook before answering its sender, and do not swallow a `DeliveryError` in a
  handler — the error is what makes the bus retry.
- Do not follow redirects when sending, and do not bound a delivery anywhere but on its client —
  set the timeout in the HTTP client configuration, not around `Transport`.
- Do not run with an empty route secret in production, and do not write a secret as a literal in
  configuration — pass `env("...")`.
- Do not queue a webhook through storage you do not trust: the subscriber secret is in the
  message body.
