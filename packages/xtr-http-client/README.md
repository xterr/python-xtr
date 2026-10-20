<div align="center">

# xtr-http-client

**An async HTTP client behind one interface: typed options in, a response read on demand out.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="asyncio" src="https://img.shields.io/badge/asyncio-native-1f6feb">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

Sending a request is the easy half. The rest — one set of defaults per host, a timeout that
means what it says, a redirect that drops the credentials it must not carry on, an address an
untrusted URL must never reach, and a way to answer from a script instead of the network in a
test — is what every application writes again.

This package implements [xtr-http-client-contracts](../xtr-http-client-contracts) and puts that
rest behind the same interface: every feature is a client wrapping a client, so the code that
calls out sees one type however much is layered under it.

## Install

```sh
uv add xtr-http-client
uv add "xtr-http-client[http2]"                   # + the framing a request asking for version "2" needs
uv add xtr-http-client xtr-dependency-injection   # + the container, for the HttpClientBundle
uv add xtr-rate-limiter                           # beside it: the limiter the throttling client paces by
uv add xtr-http-foundation                        # beside it: the networks the private-network guard refuses
```

Requires Python 3.11+. `http2` is the only extra, and the container is not a dependency: the
bundle is used when [xtr-dependency-injection](../xtr-dependency-injection) is installed beside the
package, never as an extra, and every client works without it, built by hand as below. Installed
beside it too, [xtr-rate-limiter](../xtr-rate-limiter) supplies the limiter `ThrottlingHttpClient`
paces by, and [xtr-http-foundation](../xtr-http-foundation) the networks
`NoPrivateNetworkHttpClient` refuses.

## Quick start

`HttpClient.create()` hands back a client, typed as the contract's interface, so nothing in an
application has to name an implementation:

```python
from xtr_http_client import HttpClient

client = HttpClient.create(base_uri="https://api.example.com/", timeout=5)

async with await client.request("GET", "orders", query={"paid": "1"}) as response:
    print(response.get_status_code())
    orders = await response.to_array()
```

Three things in that are worth saying out loud.

- **`request()` returns as soon as the status line and the headers are in**, and never raises
  because of the status: a 404 or a 503 is an answer. The body is read when it is asked for.
- **The body is read on demand and kept** — in a temporary file past 2 MiB — so
  `await response.get_content()` twice reads the same bytes twice, and `response.get_body()` is
  the message stream over that same kept body.
- **A response holds a connection until it is done with.** Leaving the `async with` block
  closes the body, which frees the connection; `await response.cancel()` does it mid-transfer.

`get_content()` and `to_array()` are where an unsuccessful status *is* raised —
`RedirectionError`, `ClientError`, `ServerError`. Pass `throw=False` to read the body a 4xx
came with instead:

```python
response = await client.request("GET", "orders/404")

if response.get_status_code() == 404:
    explanation = await response.get_content(throw=False)
```

`get_info()` reports the transfer without waiting and without raising, so it is readable while
one is still going on: `get_info("http_code")`, `"url"`, `"redirect_count"`, `"total_time"`,
`"response_headers"` — the raw status and header lines of every hop — and the rest the
[contract](../xtr-http-client-contracts#the-response) lists.

### Sending a message request

`send_request` takes a [message request](../xtr-http-message) that already knows its own
method, URI, headers and body. The request wins wherever both have an opinion; the options
fill in what it leaves out:

```python
from xtr_http_message import Request

request = Request("POST", "/orders", headers={"Idempotency-Key": "k-1"}, body=b'{"total":42}')

async with await client.send_request(request, headers={"Accept": "application/json"}) as response:
    created = await response.to_array()
```

So the `Idempotency-Key` is the request's, the `Accept` comes from the options, a relative URI
is resolved against `base_uri`, a `query` option is merged into the URI, and `auth_bearer`
applies only where the request carries no `Authorization` of its own. A `body` or `json`
option alongside a request that already has a body is refused rather than merged.

### Options

Every call takes the contract's [`RequestOptions`](../xtr-http-client-contracts#request-options)
as keyword arguments — `headers`, `query`, `body`, `json`, `timeout`, `max_duration`,
`max_redirects`, `proxy`, `resolve`, `verify_peer`, `base_uri`, `auth_basic`, `auth_bearer` and
the rest. An option this client does not know is refused with `InvalidArgumentError`, naming
the closest one it does, because an option spelled wrong that was quietly dropped is a setting
that silently never applied.

A `body` mapping holding a file opened `"rb"` is uploaded as `multipart/form-data` — plain
values as `data`, each file as a part named after its file and typed from that name — and a
mapping without one stays url-encoded:

```python
with open("photo.png", "rb") as photo:
    response = await client.request("POST", "upload", body={"caption": "hi", "photo": photo})
```

A `Content-Type: multipart/form-data; boundary=...` set by the caller keeps its boundary. The
file is read synchronously while the body is sent, which suits uploads of a modest size.

`with_options()` turns options into the defaults of another client of the same type, leaving
the one everyone else holds as it was:

```python
authorized = client.with_options(auth_bearer="t0ken", timeout=30)
```

## The clients

Every feature here is a client wrapping a client, all of them `HttpClientInterface`, so the
code that calls out never sees how deep the stack is.

### `HttpxHttpClient` — the one that opens connections

The transport, and what `HttpClient.create()` hands back. [httpx](https://www.python-httpx.org)
does the HTTP work and is named nowhere else, so nothing above this depends on it.

```python
from xtr_http_client import HttpxHttpClient

async with HttpxHttpClient({"timeout": 5}, max_host_connections=4) as client:
    async with await client.request("GET", "https://api.example.com/orders") as response:
        orders = await response.to_array()
```

- Connections are pooled by *how* they connect rather than by host: a proxy, a trust store, a
  client certificate, the protocol version and the deadlines each decide what a connection is,
  so every combination of them gets a pool, made the first time something asks for it.
  `max_host_connections` is each pool's ceiling across every host it reaches.
- **Proxy settings are read from the environment** — `http_proxy`, `https_proxy`, `no_proxy` —
  and are part of what picks a pool, so changing them asks for a different pool rather than
  being ignored. The `proxy` option overrides them per request.
- Redirects are followed here rather than by the backend, for the one thing a backend cannot be
  told: an `Authorization` header belongs to the host it was meant for, so it is dropped the
  moment a chain leaves that host and put back only if the chain returns to it.
- `aclose()` — or leaving the `async with` — closes every pool. Nothing is opened until a
  request is made.

What it refuses, before anything is sent: an empty method or one that is not uppercase ASCII
letters; `auth_basic` and `auth_bearer` together, or either in a shape credentials cannot be
read from; `json` and `body` together; an option it does not know; and an `http_version` other
than `"1.1"` or `"2"` — HTTP/1.0 cannot be asked for, and `"2"` without the `http2` extra is
refused by name rather than failing as a missing import.

### `ScopingHttpClient` — a set of defaults per service

A scope is a regular expression the start of a URL is matched against, and the options every
request landing in it starts from:

```python
from xtr_http_client import ScopingHttpClient

client = ScopingHttpClient(
    inner,
    {r"https://api\.example\.com/": {"auth_bearer": "t0ken", "headers": {"Accept": "*/*"}}},
)
```

The first pattern matching is the one that applies, so order them from most specific to least.
What the request itself asked for always wins — a scope fills in, it never overrides — and
`headers` is the one option merged name by name rather than replaced, so a scope-wide `Accept`
survives a request setting its own `Content-Type`.

`ScopingHttpClient.for_base_uri(inner, "https://api.example.com/", {"timeout": 10})` is the
common case said shortly: one scope over that base, which is also the scope a relative URL
resolves against. `for_base_uris(inner, [...])` is the same for a service answering at several,
the first being what relative URLs resolve against.

### `RetryableHttpClient` — make the request again while that is worth doing

```python
from xtr_http_client import GenericRetryStrategy, RetryableHttpClient

client = RetryableHttpClient(inner, GenericRetryStrategy([500, 502, 503]), max_retries=2)
```

`max_retries` is how many *further* attempts are allowed, so the request is made at most that
many times plus one; a request may lower or raise it with the `max_retries` option. A
`Retry-After` header wins over whatever delay the strategy names — a server saying when to come
back is better informed than a client guessing. The response reports how many tries it took,
under the `retry_count` entry of `get_info()`.

A body that cannot be produced twice is sent once: a second attempt would send a request that
is not the one that failed. And when `base_uri` names several, each attempt moves one along
them — how a client is pointed at a second host rather than at the one that has just refused.

`GenericRetryStrategy` is the default. It retries by status code and, where it matters, by
method: a 503 is "not now" whatever was asked, while a 500 after a `POST` may have changed
something already. Out of the box that is `DEFAULT_RETRY_STATUS_CODES` — `423`, `425`, `429`,
`502` and `503` for every method, and `0` (nothing came back), `500`, `504`, `507` and `510`
for `IDEMPOTENT_METHODS` only. The delay starts at `delay_ms` and is multiplied by `multiplier`
per attempt already made, capped by `max_delay_ms`, with `jitter` spreading it over a window so
a thousand clients that failed together do not come back together.

`RetryStrategyInterface` is the seam for a strategy of your own: `should_retry(context,
content, error)` answers `True`, `False`, or `None` for "not without the body" — the client
then reads the whole body and asks once more with it — and `get_delay(...)` says how long to
wait in milliseconds. `RetryContext` carries the attempt as it went out: the method, the
resolved URL, the merged options, the `retry_count`, the response or `None`, and
`get_status_code()`, which is `0` when nothing answered.

### `ThrottlingHttpClient` — hold requests to a pace

```python
from xtr_http_client import ThrottlingHttpClient

client = ThrottlingHttpClient(inner, limiter)
```

`limiter` is an [xtr-rate-limiter](../xtr-rate-limiter) `LimiterInterface`, from that package
installed beside this one. A token is booked before each request and the request waits for the
moment that booking is due; booking first and waiting after is what makes the pace hold under
concurrency, since requests then leave in the order they were asked for rather than all at
once. Which requests share a pace is decided by which of them are given the same limiter — one
per host, one per account, one for the whole application — and a copy made by `with_options()`
shares it.

### `TraceableHttpClient` — a record of every request made

```python
from xtr_http_client import TraceableHttpClient

client = TraceableHttpClient(inner)

async with await client.request("GET", "https://api.example.com/orders") as response:
    _ = await response.get_content()

traced = client.get_traced_requests()
assert traced[0]["method"] == "GET"
```

A `TracedRequest` is added the moment a request is made and filled in as it goes: `info` when
the response arrives — or the error alone when nothing does — and `content` once the caller
reads the body. So a trace read mid-request says how far it has got rather than nothing.

The bodies are the costly half of a record and the half most likely to carry a credential, so
`extra={"trace_content": False}` leaves them out: `body` and `json` are dropped from `options`
and `content` is `False` rather than bytes. Pass `disabled=lambda: ...` to record nothing while
it says so. There is one record per client and its copies; `reset()` clears it.

### `NoPrivateNetworkHttpClient` — refuse what leads inwards

A URL that came from outside is data, so without a guard a request is a way to make this
process reach an address only this process can see — another service on the same network, an
admin port, a metadata endpoint handing out credentials.

```python
from xtr_http_client import NoPrivateNetworkHttpClient

client = NoPrivateNetworkHttpClient(inner, allow_list=("10.1.2.3",))
```

The check runs on what the host *resolves to*, not on how it is written, and one refused
address refuses the whole request — whichever of them the connection would pick, nothing is
sent. The request is then pinned to the address that was checked, through the `resolve` option,
so a name whose records change between the check and the connection reaches what was vetted or
nothing at all. Redirects are followed here too, because a hop nobody checked would walk
straight past the guard.

A refusal is `TransportError`: `Host "<host>" is blocked for "<url>".`, or `IP "<ip>" is
blocked for "<url>".` for an address written out. With no `subnets` it refuses
`IpUtils.PRIVATE_SUBNETS` from [xtr-http-foundation](../xtr-http-foundation) — loopback,
private, link-local, carrier-grade NAT, unique-local, multicast, reserved and unspecified
alike. `subnets` replaces that set and `allow_list` opens one receiver without opening the
network it sits in; both take addresses or CIDR networks, never host names. What a host
resolved to is remembered for the client's life, and `reset()` forgets it.

xtr-http-foundation is not a dependency: install it beside this package (`uv add
xtr-http-foundation`) to use the guard. Without it, building `NoPrivateNetworkHttpClient`
raises `LogicError`, so nothing goes out unchecked.

### `MockHttpClient` — answer from a script

The same client as any other here — the options it refuses, the defaults it starts from and the
way a request and its options are merged are all the ones a real transfer uses — with the
transfer replaced by what a test wrote out. Nothing is opened.

```python
from xtr_http_client import JsonMockResponse, MockHttpClient, MockResponse

client = MockHttpClient([JsonMockResponse({"id": 7}, {"http_code": 201}), MockResponse(b"ok")])

async with await client.request("POST", "/orders") as response:
    assert response.get_status_code() == 201
    assert await response.to_array() == {"id": 7}

assert client.get_requests_count() == 1
```

Where the answers come from is whatever a test finds easiest to write: nothing, and every
request is an empty 200; one `MockResponse`, which answers one request; an iterable of them,
one per request in order; or a callable handed the method, the URL and the merged options,
which is how a test asserts on the request that was made and answers differently depending on
it — it may be async, and an iterable may hold callables too.

```python
from xtr_http_client_contracts import RequestOptions


def answer(method: str, url: str, options: RequestOptions) -> MockResponse:
    assert options["auth_bearer"] == "t0ken"
    return JsonMockResponse({"url": url})


client = MockHttpClient(answer)
```

A request past the end of an iterable is a mistake and is reported as one — a test making more
requests than it wrote answers for is no longer testing what it says. Nothing is followed and
nothing is resolved: a 3xx is the answer, and `base_uri` starts at `https://example.com` so a
test can say `/orders` and mean something. `set_response_factory(...)` changes the answers
mid-test, keeping the count; `reset()` clears the count, keeping the answers.

`MockResponse(body, info)` writes out the answer: `body` is bytes, text, or an iterable of
bytes handed over a piece at a time, and `info` is what the transfer is to claim about itself —
`http_code` (200 when left out), `response_headers`, and `error` for a transfer that is to fail
rather than answer. Any other entry is carried through to `get_info()`.
`JsonMockResponse(value, info)` encodes a value and labels it `application/json` unless the
script named a content type of its own, and `JsonMockResponse.from_file(path)` reads a recorded
document — now rather than when the response is issued, so a wrong path is reported where it
was written.

A written response is half a response: the method, the URL and the options it answers are the
client's, filled in when the client issues it. Reading one no client issued raises
`InvalidArgumentError`, and `get_request_method()`, `get_request_url()` and
`get_request_options()` are what a test asserts the issued half on.

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what
removing it undoes.

- **Install** — `uv add xtr-http-client xtr-dependency-injection`: the bundle needs the container
  installed beside it, never as an extra. Add `http2` to ask for HTTP/2, and install
  [xtr-rate-limiter](../xtr-rate-limiter) beside it to pace a client with one of its limiters.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Activate* step below: it lists
  `HttpClientBundle`. There is no config file, environment or ignore line to write; it prints the
  step to name the services the application calls in `config/http_client.py`, which a recipe
  cannot make for you (see [xtr-recipes](../xtr-recipes)).
- **Activate** — `HttpClientBundle: {"all": True}` in `BUNDLES` in `<app>/bundles.py`,
  imported from `xtr_http_client.bundle`.
- **Brings along** — the rate limiter bundle when xtr-rate-limiter is installed.
- **Configure** — optional: with no configuration there is one client, an
  `HttpClientInterface` sending requests as they are given. Default options, a client per
  service, retries, a pace and a mock for tests go in `<app>/config/http_client.py`, a
  `@configure` function returning `HttpClientConfig` — see [Kernel / bundle](#kernel--bundle).
- **Environment** — nothing. A credential given as `env(...)` is read when the client needing
  it is built.
- **Ignore** — nothing.
- **Remove** — drop the `BUNDLES` entry, delete `<app>/config/http_client.py`, then
  `uv remove xtr-http-client`.
- **Check** — `debug:bundles` shows `http_client` as `listed` and `active`.

## Kernel / bundle

With [xtr-dependency-injection](../xtr-dependency-injection) installed beside the package — it is
not a dependency, and nothing outside `xtr_http_client.bundle` needs it — list the bundle, then
configure the clients:

```python
# app/bundles.py
from xtr_http_client.bundle import HttpClientBundle

BUNDLES = {HttpClientBundle: {"all": True}}
```

```python
# app/config/http_client.py
from xtr_dependency_injection import configure, env

from xtr_http_client.bundle import (
    ClientOptionsConfig,
    HttpClientConfig,
    RetryFailedConfig,
    ScopedClientConfig,
)


@configure
def http_client() -> HttpClientConfig:
    return HttpClientConfig(
        default_options=ClientOptionsConfig(
            timeout=10, retry_failed=RetryFailedConfig(enabled=True)
        ),
        scoped_clients={
            "github": ScopedClientConfig(
                base_uri="https://api.github.com/",
                headers={"Accept": "application/vnd.github+json"},
                auth_bearer=env("GITHUB_TOKEN"),
            ),
        },
    )
```

The default client is the unqualified `HttpClientInterface`; each scoped client is the
`HttpClientInterface` qualified by its name:

```python
from typing import Annotated

from xtr_dependency_injection import Target, as_service
from xtr_http_client_contracts import HttpClientInterface


@as_service
class GithubRepositories:
    def __init__(self, github: Annotated[HttpClientInterface, Target("github")]) -> None:
        self._github = github
```

`HttpClientConfig`:

| Field | Default | What it sets |
|---|---|---|
| `max_host_connections` | `6` | how many connections one pool may hold |
| `default_options` | `ClientOptionsConfig()` | what every request starts from, and the default client's layers |
| `scoped_clients` | `{}` | a client per service, by name |
| `mock_response_factory` | `False` | answer every request from `MockHttpClient` instead of the network |
| `tracing` | `False` | wrap every client in a `TraceableHttpClient` |

`ClientOptionsConfig` carries the request options of the same name — `headers`, `timeout`,
`max_redirects`, `proxy`, `verify_peer` and the rest, `None` leaving each to the client — and
two layers: `retry_failed`, a `RetryFailedConfig` (`enabled`, `max_retries`, `delay`,
`multiplier`, `max_delay`, `jitter`, `http_codes`, `base_uris`, or a `retry_strategy` service
instead of the numbers), and `rate_limiter`, the name of the xtr-rate-limiter limiter requests
wait their turn from. `ScopedClientConfig` adds `scope` or `base_uri` (one is required),
`auth_basic`, `auth_bearer`, `query` and its own `mock_response_factory`; the
`retry_failed` and `rate_limiter` it leaves unset are the default options' own.

Each client is built, from the inside out, as the transport, the pace of its limiter, its
scope, its retries — outside the scope when they move along `base_uris` — and the trace.
Every client shares one transport, and so its connections; nothing is opened until a request
is made, and the connections are closed with the container. With `mock_response_factory`, the
`MockHttpClient` service is the transport: a test scripts it with `set_response_factory`.

## Errors

The hierarchy is the [contract's](../xtr-http-client-contracts#errors), re-exported from
`xtr_http_client.exception` so one import answers "what can this client raise":

| Error | Raised when |
|---|---|
| `HttpClientError` | the root of all of them |
| `TransportError` | no answer came — a refused connection, a broken transfer, a cancelled response, a guarded address |
| `TransportTimeoutError` | no answer came in time; a `TransportError` |
| `HttpError` | there is an answer and it is not a success |
| `RedirectionError` | a 3xx read with `throw`, once `max_redirects` was reached |
| `ClientError` | a 4xx read with `throw` |
| `ServerError` | a 5xx read with `throw` |
| `DecodingError` | the body is not what it was read as |
| `JsonError` | the body is not the JSON object it was read as; a `DecodingError` |
| `InvalidArgumentError` | the request is one a client refuses to make, before anything is sent |

An unsuccessful status names itself: `HTTP 404 returned for "<url>".`, the status line the
server sent, or the `title` and `detail` of the body when that body is a JSON error document.

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-http-client`; run the commands below from there. The `python-xtr-http-client`
repository is a read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync --all-extras
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
