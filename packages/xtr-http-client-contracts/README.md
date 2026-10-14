<div align="center">

# xtr-http-client-contracts

**The async HTTP client contract, and nothing else — so a library that calls out installs no backend.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="asyncio" src="https://img.shields.io/badge/asyncio-native-1f6feb">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

A library that sends an HTTP request should not choose what sends it. It takes the client
interface, asks for a method and a URL, and leaves connection pooling, redirects and TLS to
whatever the application wired behind it.

That needs the *seam*, not a client. This package is that seam: the client interface, the
response interface, the typed request options, the errors they raise, and a conformance suite
any implementation runs against itself.

## Install

```sh
uv add xtr-http-client-contracts
uv add --dev "xtr-http-client-contracts[testing]"   # + what the conformance suite runs on
```

Requires Python 3.11+. The only runtime dependency beyond `typing-extensions` is
[xtr-http-message-contracts](../xtr-http-message-contracts): a client response is an HTTP
response before it is anything else.

## What a caller depends on

```python
from xtr_http_client_contracts import HttpClientInterface


async def paid_orders(client: HttpClientInterface) -> dict[str, object]:
    response = await client.request("GET", "https://api.example.com/orders", query={"paid": "1"})
    async with response:
        return await response.to_array()
```

`HttpClientInterface` is a `@runtime_checkable` `Protocol` with three members:

| Member | Answers |
|---|---|
| `await request(method, url, **options)` | an `HttpResponseInterface`, once the status line and the headers are in |
| `await send_request(request, **options)` | the same, for a [message request](../xtr-http-message-contracts) that already knows its own method, URI, headers and body |
| `with_options(**options)` | another client of the same type, whose defaults are these options over this one's |

Neither call raises because of the status: a 404 or a 503 is an answer and comes back as a
response. What they do raise is `TransportError` when nothing answered,
`TransportTimeoutError` when nothing answered in time, and `InvalidArgumentError` for a
method, a URL or an option that is refused before anything is sent.

`send_request` says what wins when a request and the options both have an opinion: the request
is authoritative. A relative URI is resolved against `base_uri`, `query` is merged into the
URI, a header from `headers` is sent only under a name the request does not carry,
`auth_basic` and `auth_bearer` apply only without an `Authorization` of the request's own, and
`body` or `json` alongside a request that already carries a body is refused, word for word:

```
Define either the request body or the "body" or "json" option, setting both is not supported.
```

Several requests run at once by being made from tasks of one task group; nothing in the
contract is per client state a caller has to serialize.

## The response

`HttpResponseInterface` extends the message `ResponseInterface`, so the status code, the reason
phrase, the protocol version, the headers, `get_body()` and the `with_*` copies are the message
contract's — code typed against the plain response interface takes one of these as it is, and
`isinstance` is what reveals the extras:

```python
from xtr_http_client_contracts import HttpResponseInterface
from xtr_http_message_contracts import ResponseInterface


def log(response: ResponseInterface) -> None:
    print(response.get_status_code())
    if isinstance(response, HttpResponseInterface):
        print(response.get_info("total_time"))
```

What a client adds on top of a message response:

| Member | Is |
|---|---|
| `await get_content(throw=True)` | every byte of the body, waiting for the rest of it to arrive |
| `await to_array(throw=True)` | that body decoded as a JSON object |
| `get_info(key=None)` | what the transfer knows about itself, never waiting and never raising |
| `await cancel()` | the transfer abandoned, and what it held let go of |
| `async with response:` | a block that owns the transfer and closes the body on the way out |

`throw` is the one switch: left on, an unsuccessful status is raised by reading the body —
`RedirectionError`, `ClientError`, `ServerError` — rather than returned. `throw=False` hands
the body over whatever the status says, which is how a 4xx carrying an explanation is read.

`get_info()` always answers these entries: `canceled`, `error`, `http_code` (`0` before a
status arrived), `http_method`, `redirect_count`, `redirect_url`, `response_headers` (the raw
status and header lines of every hop), `start_time`, `total_time`, `url` and `user_data`.
`primary_ip` and `retry_count` are there when they are known. Because it neither waits nor
raises, it is readable while the transfer is still going on.

## Request options

`RequestOptions` is a `total=False` `TypedDict`, so every option is checked where it is
written and an option left out is one nobody asked about — the client fills it in from its own
defaults, which start at `OPTIONS_DEFAULTS`.

```python
from xtr_http_client_contracts import OPTIONS_DEFAULTS, RequestOptions

defaults: RequestOptions = {**OPTIONS_DEFAULTS, "timeout": 5, "max_redirects": 0}
```

| Option | Says |
|---|---|
| `auth_basic`, `auth_bearer` | the credentials to send; both at once is refused |
| `query` | parameters merged into the URL, winning over one of the same name already there |
| `headers` | the headers to send, one value or several per name |
| `body`, `json` | what to send — bytes, text, a mapping as a form, an async iterable produced as it goes; or a value encoded as JSON. Both at once is refused |
| `user_data` | anything to find again under the `user_data` entry of `get_info()`; never read |
| `max_redirects` | how many hops to follow; zero or less answers with the 3xx |
| `http_version` | `"1.0"`, `"1.1"`, `"2"` or `"2.0"`; `None` leaves it to the connection |
| `base_uri` | what a relative URL resolves against. A sequence of them is for a client that retries, which moves along it |
| `timeout` | how long the transfer may go quiet for. `None` is 60 seconds, not "no limit" |
| `max_duration`, `max_connect_duration` | limits on the whole request and on connecting. Zero *is* "no limit" |
| `resolve` | host to address, instead of asking a resolver — what pins a request to an address already checked |
| `proxy` | the proxy to go through, as a URL |
| `verify_peer`, `verify_host`, `cafile`, `capath`, `local_cert`, `local_pk`, `passphrase` | how the peer is checked, and what is presented to it |
| `max_retries` | how many further attempts a client that retries may make |
| `extra` | options a client may ignore where it has no use for them — `use_persistent_connections`, `trace_content` |

A name the contract does not list is refused rather than quietly obeyed, with
`InvalidArgumentError`:

```
Unsupported option "timout" passed to "HttpxHttpClient", did you mean "timeout"?
```

That refusal is the point of naming them: an option spelled wrong cannot pass for one that was
obeyed. `extra` is the escape hatch for what one client understands and another has no use
for, so entries in it may be ignored.

## Errors

Everything derives from `HttpClientError`, and the shape of the tree is the question a caller
asks: was there an answer at all, and was it the one wanted?

| Error | Raised when |
|---|---|
| `HttpClientError` | the root; nothing raises it directly |
| `TransportError` | no answer came — a refused connection, a broken transfer, a cancelled response |
| `TransportTimeoutError` | no answer came in time; a `TransportError` |
| `HttpError` | there is an answer and it is not a success |
| `RedirectionError` | a 3xx read with `throw`, once `max_redirects` was reached |
| `ClientError` | a 4xx read with `throw` |
| `ServerError` | a 5xx read with `throw` |
| `DecodingError` | the body is not what it was read as |
| `JsonError` | the body is not the JSON object it was read as; a `DecodingError` |
| `InvalidArgumentError` | the request is one the client refuses to make, before anything is sent |

The message of an `HttpError` names the code and the URL — `HTTP 404 returned for "<url>".` —
or quotes the status line the server sent, and takes the `title` and `detail` of the body when
that body is a JSON error document.

## The conformance suite

`xtr_http_client_contracts.testing` is how an implementation proves it is one. It ships in
`src` rather than in `tests` because it is run by other packages; install it with the
`testing` extra, which brings an async backend, the runner the suite is written for, and a
message request implementation.

Subclass `HttpClientTestCase` and return the client under test:

```python
# tests/integration/test_my_http_client.py
from xtr_http_client_contracts import HttpClientInterface
from xtr_http_client_contracts.testing import HttpClientTestCase

from my_package import MyHttpClient


class TestMyHttpClient(HttpClientTestCase):
    def create_client(self) -> HttpClientInterface:
        return MyHttpClient()
```

That is the whole of it: the suite starts `TestHttpServer` once for the session, points every
test at it, and runs the contract as behaviour — the status that is an answer, the body that is
kept and can be read twice, the redirect chain that drops credentials when it leaves the host
and gets them back when it returns, the timeouts, the proxy settings read from the
environment, the `resolve` pin, the options `send_request` fills in, and the refusals quoted
above. A client that passes is one a caller can hold through the interface alone.

`create_client` is called per test, freshly: a test may cancel a transfer or exhaust a pool, so
no two tests share a client. A client that cannot honour part of the contract yet says which
tests it skips and why, rather than quietly not running them:

```python
from collections.abc import Mapping
from typing import ClassVar


class TestMyHttpClient(HttpClientTestCase):
    skipped_tests: ClassVar[Mapping[str, str]] = {
        "test_ipv6_resolve": "no IPv6 in this environment",
    }
```

A parametrized test is named there without its parameter. `TestHttpServer(host=..., port=...)`
is usable on its own — as a context manager, or with `start()` and `stop()` — for a test that
needs a second server of its own.

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-http-client-contracts`; run the commands below from there. The
`python-xtr-http-client-contracts` repository is a read-only copy, so send issues and pull
requests to the monorepo.

```sh
uv sync --all-extras
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

[xtr-http-client](../xtr-http-client) is the implementation, and runs this suite against each
of its clients.

## License

MIT — see [LICENSE](LICENSE).
