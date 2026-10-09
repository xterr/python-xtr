<div align="center">

# xtr-http-message-contracts

**The HTTP message contract, and nothing else — so two libraries can pass a request between them without agreeing on a class.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="core dependencies: 1" src="https://img.shields.io/badge/core%20deps-1-3FB950">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

An authorization server, a rate limiter and a firewall all read a request and fill in a response.
None of them should care whose request object it is — and if each brings its own, the application
ends up converting between three shapes of the same thing on every call.

So they need the *seam*, not an implementation. This package is that seam and nothing else:
thirteen protocols and an enumeration, built from the standard library, with one dependency —
`typing-extensions`, for `@override` on 3.11.

- 🧩 **`ServerRequestInterface`** — what arrived: method, URI, headers, body, cookies, query,
  uploaded files, parsed body, plus the attributes a handler annotates it with.
- 📤 **`ResponseInterface`** — a status code, a reason phrase, headers and a body.
- 🌊 **`StreamInterface`** — the body itself, as a cursor over bytes.
- 🔗 **`UriInterface`** — a URI taken apart into components and put back together as text.
- 📎 **`UploadedFileInterface`** / **`UploadError`** — a file that came in, and how it went.
- 🏭 **Six factories** — build any of the above without naming a class.

```python
from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface


def whoami(request: ServerRequestInterface, response: ResponseInterface) -> ResponseInterface:
    _ = response.get_body().write(request.get_header_line("user-agent").encode())
    return response.with_header("content-type", "text/plain")
```

## Install

```sh
uv add xtr-http-message-contracts
```

Requires Python 3.11+.

## Who installs what

|  | Depends on |
| --- | --- |
| **A library that handles requests** | `xtr-http-message-contracts` at runtime, `xtr-http-message` as a dev dependency — its tests build real messages. |
| **An application** | `xtr-http-message`, which implements the contract, plus the integration that bridges these types to the web framework it runs on. |

An implementation **builds on** these types rather than redefining them. Import them from
`xtr_http_message_contracts`; that one set of types is what lets a container register an
implementation under an interface, and a library that never imported the implementation receive
it.

## The interfaces

| Interface | What it is |
| --- | --- |
| `MessageInterface` | What a request and a response share: protocol version, headers, body. |
| `RequestInterface` | A message going out: a method and a URI on top. |
| `ServerRequestInterface` | A request that arrived, with everything the server learned alongside it. |
| `ResponseInterface` | A message coming back: a status code and a reason phrase on top. |
| `StreamInterface` | A message body: read, write, seek, and the whole of it in one call. |
| `UriInterface` | A URI as a value, every component readable. |
| `UploadedFileInterface` | One file that came in with a request, movable once. |

Under `xtr_http_message_contracts.factory`, one factory each for a request, a server request, a
response, a stream, a URI and an uploaded file — `RequestFactoryInterface`,
`ServerRequestFactoryInterface`, `ResponseFactoryInterface`, `StreamFactoryInterface`,
`UriFactoryInterface`, `UploadedFileFactoryInterface`. They are re-exported at the top level too,
so either import works.

The rules that hold across all of them:

- **Messages are immutable.** Every `with_*` method leaves the instance it was called on as it
  was and returns one carrying the change, so a message handed on cannot be altered behind the
  caller's back. The return type is `Self`, so a subtype keeps its own type through a chain.
- **Header names are matched without regard to case**, and reported in the case they were first
  given in. A header the message does not carry reads as an empty sequence from `get_header` and
  an empty string from `get_header_line` — never as an error.
- **A component the URI has not got reads as an empty string**, and `get_port` reads as `None`
  when there is no port worth reporting.
- **A stream is the one thing that is not immutable**: reading, writing and seeking move its
  cursor in place. Its payload is `bytes`, since a body may be binary; `bytes(stream)` rewinds
  and reads the whole of it, and never raises.
- **`with_uri` decides the `Host` header.** By default it follows the new URI, and a `Host`
  header already there carries over only when the URI has no host; `preserve_host=True` keeps a
  non-empty one exactly as it is.

### Upload errors

`get_error()` on an uploaded file, and `error=` when building one, carry one of these:

| Member | Value | Means |
| --- | --- | --- |
| `OK` | 0 | The file arrived whole. |
| `INI_SIZE` | 1 | Larger than the server configuration allows. |
| `FORM_SIZE` | 2 | Larger than the submitted form named. |
| `PARTIAL` | 3 | The upload stopped part way. |
| `NO_FILE` | 4 | The field was submitted with no file in it. |
| `NO_TMP_DIR` | 6 | Nowhere to keep the file while receiving it. |
| `CANT_WRITE` | 7 | It could not be written to where it was being kept. |
| `EXTENSION` | 8 | Something loaded on the server refused it. |

`UploadError` is an `IntEnum`, so a member passes anywhere the `int` the contract calls for is
expected. `5` is absent because that number was never assigned.

## What is not here

Anything that *is* a message rather than describing one: the request, response, stream, URI and
uploaded file classes, the status-code phrase table, URI parsing, and the factory that builds all
six. That is `xtr-http-message`.

Anything that bridges a message to a web framework — building one from the call in flight,
returning one from a route, registering either on a container — is not here either: it belongs
with that framework's integration, which for a FastAPI application is
[xtr-http-kernel](../xtr-http-kernel).

## Errors

This package defines no exception of its own; a contract with no behaviour has nothing to raise.
The interfaces name two builtins instead, so a caller catches the same thing whichever
implementation is behind them:

| Error | Raised when |
| --- | --- |
| `ValueError` | An argument cannot be what it is being used as — a malformed header name, an out-of-range port, a status code that is not one |
| `RuntimeError` | An operation cannot be carried out now — a stream that will not seek, an uploaded file already moved |

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-http-message-contracts`; run the commands below from there. The
`python-xtr-http-message-contracts` repository is a read-only copy, so send issues and pull
requests to the monorepo.

```sh
uv sync
uv run ruff check . && uv run ruff format --check .
uv run basedpyright
uv run ty check
uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
