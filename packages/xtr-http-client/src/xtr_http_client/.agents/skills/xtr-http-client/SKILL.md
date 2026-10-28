---
name: xtr-http-client
description: How to call out over HTTP with xtr-http-client and the xtr-http-client-contracts interfaces it implements — typed request options, a response whose body is read on demand, scoped clients per service, retries, a pace, a trace, a private-network guard, and a mock client for tests. Use when code must fetch or post to another service; when a 4xx or 5xx has to be handled rather than raised; when you need per-service credentials, base URIs, timeouts, redirects without leaking an Authorization header, retry with backoff, rate-paced outbound calls, or an SSRF guard on a URL that came from a user; when writing a test that must not touch the network; and when adding HttpClientBundle to an application or configuring its default and scoped clients.
---

# xtr-http-client

A library that calls out depends on `HttpClientInterface` from
[xtr-http-client-contracts](https://github.com/xterr/python-xtr/tree/main/packages/xtr-http-client-contracts);
this package is what an application puts behind it. Every feature is a client wrapping a
client, so the calling code sees one type however deep the stack is.

## Quick reference

- `HttpClient.create(max_host_connections=6, **default_options)` → an `HttpClientInterface`.
- `await client.request(method, url, **options)` returns once the status line and headers are
  in. **It never raises because of the status** — a 404 is an answer.
- `await client.send_request(message_request, **options)` sends a message request; the request
  wins wherever both have an opinion.
- `client.with_options(**options)` → another client of the same type with those defaults.
- Reading: `await response.get_content(throw=True)`, `await response.to_array(throw=True)`,
  `response.get_body()` (the message stream), `response.get_info(key=None)`,
  `await response.cancel()`. `throw` is what raises `ClientError` / `ServerError` /
  `RedirectionError`.
- `async with await client.request(...) as response:` frees the connection on the way out.
- Clients: `HttpxHttpClient` (the transport), `ScopingHttpClient`, `RetryableHttpClient`,
  `ThrottlingHttpClient`, `TraceableHttpClient`, `NoPrivateNetworkHttpClient`,
  `MockHttpClient`.
- Options are the contract's `RequestOptions`. An option it does not know is refused, never
  ignored.
- In an application, with xtr-dependency-injection installed beside the package (it is not a
  dependency): activate `HttpClientBundle` and inject `HttpClientInterface`. Without the
  container, build the clients yourself; only `xtr_http_client.bundle` needs it.

## Make a request

```python
from xtr_http_client import HttpClient

client = HttpClient.create(base_uri="https://api.example.com/", timeout=5)

async with await client.request("GET", "orders", query={"paid": "1"}) as response:
    if response.get_status_code() == 404:
        missing = await response.get_content(throw=False)
    else:
        orders = await response.to_array()
```

- The body is read on demand and **kept** — in a temporary file past 2 MiB — so two reads give
  the same bytes, and `response.get_body()` is the message stream over that kept body.
- `get_info()` never waits and never raises, so it is readable mid-transfer: `"http_code"`,
  `"url"`, `"redirect_count"`, `"redirect_url"`, `"total_time"`, `"response_headers"` (the raw
  lines of every hop), `"canceled"`, `"error"`, `"user_data"`.
- `timeout` is how long the transfer may go quiet for, and `None` means 60 seconds, not "no
  limit". `max_duration` and `max_connect_duration` of `0` *are* "no limit".

```python
from xtr_http_message import Request

request = Request("POST", "/orders", headers={"Idempotency-Key": "k-1"}, body=b'{"total":42}')
response = await client.send_request(request, headers={"Accept": "application/json"})
```

The request's header is the one sent, the options fill the names it lacks, a relative URI is
resolved against `base_uri`, `query` is merged into the URI, and `auth_bearer` applies only
where the request has no `Authorization`. A `body` or `json` option plus a request that already
carries a body is refused.

## Upload a file

```python
with open("photo.png", "rb") as photo:
    response = await client.request("POST", "upload", body={"caption": "hi", "photo": photo})
```

- A `body` mapping holding a binary file (`open(..., "rb")`, `io.BytesIO`) is sent as
  `multipart/form-data`; without one it stays url-encoded.
- Each file part is named after the file's `name` (`unknown` without one) and typed by
  `mimetypes.guess_type`, else `application/octet-stream`.
- Beside a file, every value is a scalar or a list of scalars; a nested one raises
  `InvalidArgumentError` naming the field — `json.dumps` it first.
- A caller-set `Content-Type: multipart/form-data; boundary=...` keeps its boundary; do not set
  a multipart content type without one.
- The file is read synchronously while the body is sent: keep the file open until `request()`
  returns, and keep uploads modest in size.
- `MockHttpClient` hands the mapping, file included, to the script as given.

## Give each service its own defaults

```python
from xtr_http_client import ScopingHttpClient

github = ScopingHttpClient.for_base_uri(
    inner,
    "https://api.github.com/",
    {"auth_bearer": token, "headers": {"Accept": "application/vnd.github+json"}},
)
```

`ScopingHttpClient(inner, {regexp: options}, default_regexp=None)` is the general form: the
first pattern matching the start of a URL applies, so order from most specific to least. What
the request asked for always wins; `headers` is the one option merged name by name.
`for_base_uris(inner, [...])` covers a service answering at several, the first resolving
relative URLs.

## Retry what is worth retrying

```python
from xtr_http_client import GenericRetryStrategy, RetryableHttpClient

client = RetryableHttpClient(inner, GenericRetryStrategy([500, 502, 503]), max_retries=2)
```

- `max_retries` is how many **further** attempts are allowed; a request may change it with the
  `max_retries` option. The response reports `get_info("retry_count")`.
- A `Retry-After` header wins over the strategy's delay.
- A body that cannot be produced twice is sent once — a second attempt would send a different
  request.
- `base_uri` naming several makes each attempt move one along them.
- `GenericRetryStrategy(status_codes, delay_ms=1000, multiplier=2.0, max_delay_ms=0,
  jitter=0.1)`: the default `DEFAULT_RETRY_STATUS_CODES` retries `423`, `425`, `429`, `502` and
  `503` for every method, and `0` (nothing answered), `500`, `504`, `507`, `510` for
  `IDEMPOTENT_METHODS` only.
- A strategy of your own implements `RetryStrategyInterface`: `await should_retry(context,
  content, error)` answers `True`, `False`, or `None` for "not without the body" — asked once
  more with it — and `get_delay(...)` returns milliseconds. `RetryContext` carries `method`,
  `url`, `options`, `retry_count`, `response`, `get_status_code()` (`0` when nothing answered).

## Pace, trace, guard

```python
from xtr_http_client import NoPrivateNetworkHttpClient, ThrottlingHttpClient, TraceableHttpClient

paced = ThrottlingHttpClient(inner, limiter)  # a LimiterInterface from xtr-rate-limiter
traced = TraceableHttpClient(inner)
guarded = NoPrivateNetworkHttpClient(inner, allow_list=("10.1.2.3",))
```

- **Throttling** books a token before each request and waits for its turn, so the pace holds
  under concurrency. Requests sharing a limiter share the pace; `with_options()` keeps it.
- **Tracing** fills `client.get_traced_requests()` as requests go on — a `TracedRequest` has
  `method`, `url`, `options`, `info`, `content`. `extra={"trace_content": False}` drops the
  bodies (`content` is then `False`); `disabled=lambda: ...` records nothing while it says so.
- **The guard** is the SSRF answer for a URL that came from outside. It checks what the host
  *resolves to*, refuses the whole request if any address is refused, pins the request to the
  checked address through `resolve`, and follows redirects itself so no hop goes unchecked.
  Refusal is `TransportError`: `Host "<host>" is blocked for "<url>".`. Without `subnets` it
  refuses `IpUtils.PRIVATE_SUBNETS`; `allow_list` opens one receiver. Addresses and CIDR
  networks only — never host names.
  It needs xtr-http-foundation installed beside this package (`uv add xtr-http-foundation`);
  without it, building the guard raises `LogicError`.

## Use the transport directly

```python
from xtr_http_client import HttpxHttpClient

async with HttpxHttpClient({"timeout": 5}, max_host_connections=4) as client:
    response = await client.request("GET", "https://api.example.com/orders")
```

Connections are pooled by how they connect — proxy, trust store, client certificate, protocol
version, deadlines — so each combination gets a pool, made on first use; `max_host_connections`
is each pool's ceiling. `http_proxy`, `https_proxy` and `no_proxy` are read from the
environment and are part of what picks a pool; the `proxy` option overrides them. Redirects are
followed here, not by the backend, so an `Authorization` is dropped when a chain leaves its host
and restored only if it returns. `await client.aclose()` closes every pool.

## Testing

`MockHttpClient` is the same client with the transfer replaced by a script: the same refusals,
the same defaults, the same merging. Nothing is opened.

```python
import pytest
from xtr_http_client import JsonMockResponse, MockHttpClient, MockResponse


@pytest.mark.anyio
async def test_it_reads_the_created_order() -> None:
    client = MockHttpClient(JsonMockResponse({"id": 7}, {"http_code": 201}))

    async with await client.request("POST", "/orders") as response:
        assert response.get_status_code() == 201
        assert await response.to_array() == {"id": 7}

    assert client.get_requests_count() == 1
```

- Answers come from nothing (every request an empty 200), one `MockResponse`, an iterable of
  them one per request, or a callable `(method, url, options) -> MockResponse` — which may be
  async, and is how a test asserts on the request that was made. An iterable may hold callables.
- A request past the end of an iterable raises `TransportError`: a test making more requests
  than it wrote answers for is not testing what it says.
- `MockResponse(body, info)`: `body` is bytes, text, or an iterable of bytes handed over piece
  by piece; `info` takes `http_code` (200 by default), `response_headers`, and `error` for a
  transfer that fails instead of answering. `JsonMockResponse(value, info)` encodes a value and
  labels it `application/json`; `JsonMockResponse.from_file(path)` reads a recorded document.
- Nothing is followed and nothing is resolved — a 3xx is the answer — and `base_uri` starts at
  `https://example.com`, so `"/orders"` means something.
- Assert the request on the issued response: `get_request_method()`, `get_request_url()`,
  `get_request_options()`. `set_response_factory(...)` changes the answers and keeps the count;
  `await client.reset()` clears the count and keeps the answers.
- A client of your own proves it is one by subclassing `HttpClientTestCase` from
  `xtr_http_client_contracts.testing` (the `testing` extra) and returning it from
  `create_client()`; the suite runs the whole contract against its own fixture server.

## Use in an application

`uv run xtr-recipes recipes:sync` applies the recipe shipped with this package: it lists
`HttpClientBundle`. There is no config file, environment or ignore line to write; it prints the
step to name the services the application calls, which a recipe cannot make for you.

1. **Install** — `uv add xtr-http-client xtr-dependency-injection`: the bundle needs the container
   installed beside it, never as an extra. Add `http2` to ask for HTTP/2, and install
   xtr-rate-limiter beside it to pace a client with one of its limiters.
2. **Activate** — `HttpClientBundle: {"all": True}` in `BUNDLES` in `<app>/bundles.py`
   (`from xtr_http_client.bundle import HttpClientBundle`).
3. **Brings along** — the rate limiter bundle when xtr-rate-limiter is installed.
4. **Configure** — optional: with no configuration there is one client sending requests as they
   are given. Otherwise `<app>/config/http_client.py`:

   ```python
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

   `HttpClientConfig` also takes `max_host_connections` (`6`), `mock_response_factory`
   (`False` — answer from `MockHttpClient` instead of the network) and `tracing` (`False`).
   `ScopedClientConfig` needs one of `scope` or `base_uri`, and adds `auth_basic`,
   `auth_bearer`, `query` and its own `mock_response_factory`.
5. **Environment** — nothing. A credential given as `env(...)` is read when the client needing
   it is built.
6. **Use** — the default client is the unqualified `HttpClientInterface`; a scoped one is the
   same interface qualified by its name:

   ```python
   from typing import Annotated

   from xtr_dependency_injection import Target, as_service
   from xtr_http_client_contracts import HttpClientInterface


   @as_service
   class GithubRepositories:
       def __init__(self, github: Annotated[HttpClientInterface, Target("github")]) -> None:
           self._github = github
   ```

7. **Check** — `debug:bundles` shows `http_client` as `listed` and `active`.
8. **Remove** — drop the `BUNDLES` entry, delete `<app>/config/http_client.py`, then
   `uv remove xtr-http-client`.

## Errors

Everything derives from `HttpClientError`; import from `xtr_http_client.exception` or from
`xtr_http_client_contracts`.

| Error | Raised when |
| --- | --- |
| `TransportError` | no answer came — refused connection, broken transfer, cancelled response, guarded address |
| `TransportTimeoutError` | no answer came in time; a `TransportError` |
| `HttpError` | there is an answer and it is not a success |
| `RedirectionError` | a 3xx read with `throw`, once `max_redirects` was reached |
| `ClientError` | a 4xx read with `throw` |
| `ServerError` | a 5xx read with `throw` |
| `DecodingError` | the body is not what it was read as |
| `JsonError` | the body is not the JSON object it was read as; a `DecodingError` |
| `InvalidArgumentError` | a request a client refuses to make, before anything is sent |

An `HttpError` names itself: `HTTP/1.1 404 Not Found returned for "<url>".`, or the `title` and
`detail` of the body when that body is a JSON error document.

## Do not

- Do not expect `request()` to raise for a 404 or a 503 — read the status, or read the body
  with `throw` left on.
- Do not read a body without owning the transfer: use `async with`, or `await
  response.cancel()`, or the connection is held until the response is collected.
- Do not pass an option the contract does not name — it is refused. Put what one client
  understands and another ignores in `extra`.
- Do not set `auth_basic` and `auth_bearer` together, or `json` and `body` together: both are
  refused.
- Do not set `timeout=None` meaning "wait forever" — it is 60 seconds. Use `max_duration=0` for
  no whole-request limit.
- Do not fetch a URL that came from a user without `NoPrivateNetworkHttpClient`, and do not
  give it host names in `subnets` or `allow_list`.
- Do not retry a non-idempotent request by listing its status code for every method; keep
  `IDEMPOTENT_METHODS` for the codes where a repeat could change something twice.
- Do not read a `MockResponse` no client issued — it raises `InvalidArgumentError`. Let
  `MockHttpClient` issue it.
- Do not reach for `xtr_http_client.internal`: it is this package's own, and nothing there is
  part of the contract.
