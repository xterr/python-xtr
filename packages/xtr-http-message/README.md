<div align="center">

# xtr-http-message

**The HTTP message contract, implemented — six small classes, one factory, and no web framework anywhere in sight.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="core dependencies: 3" src="https://img.shields.io/badge/core%20deps-3-3FB950">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

A library that handles requests should depend on the contract alone. An application has to pick
something that actually *is* a request — and that is what this package is: the thirteen
interfaces of [xtr-http-message-contracts](../xtr-http-message-contracts) made real, and nothing
besides.

- 📨 **`Request`** — a request going out: a method, a URI, headers and a body, with the `Host`
  header taken from the URI and sent in front of every other header.
- 📥 **`ServerRequest`** — a request that arrived: the environment parameters, the cookies, the
  query string parsed, the files that came with it, the parsed body, and the attributes a
  handler annotates it with.
- 📤 **`Response`** — a status code, the reason phrase recommended for it, headers and a body.
- 🌊 **`Stream`** — a body, as a cursor over bytes behind an open binary file object.
- 🔗 **`Uri`** — a URI taken apart into components and put back together as text, read as
  RFC 3986 defines one.
- 📎 **`UploadedFile`** — one file that came in, movable once.
- 🏭 **`HttpFactory`** — all six factory interfaces behind one object.

```python
from xtr_http_message import Response, ServerRequest

request = ServerRequest("GET", "https://example.com/orders?page=2")
assert request.get_query_params() == {"page": "2"}
assert request.get_header_line("host") == "example.com"

response = Response(201, {"content-type": "application/json"}, b'{"id": 7}')
assert response.get_reason_phrase() == "Created"
```

## Install

```sh
uv add xtr-http-message
```

Requires Python 3.11+. Three runtime dependencies: the contract it implements,
`typing-extensions` for `@override` on 3.11, and `uritools` to split a URI the way RFC 3986
defines it.

## Who installs what

|  | Depends on |
| --- | --- |
| **A library that handles requests** | `xtr-http-message-contracts` at runtime, this package as a dev dependency — its tests need real messages. |
| **An application** | this package, plus the integration that bridges these types to the web framework it runs on. |

An application installs it and then mostly does not name it. Code that is **serving a request**
takes the registered factory interfaces and is handed whatever the integration put behind them;
the classes here are what code *outside* a served request builds — a test, a worker, a console
command. The [response rule](#responses-in-a-served-application) below says why that matters
most for responses.

### Responses in a served application

In an application, a response is either the injected `ResponseInterface` or one the injected
`ResponseFactoryInterface` made, and every response a `with_*` on one of those returns is of
that same kind: the integration's own, returned from the route as it is, with nothing to
configure. `Response` here is *not* that — it knows no web framework, so one returned from a
route is not a response a framework can send. Build it where there is no request being served,
and have the integration convert a message that arrived from such a place: for a FastAPI
application that is [xtr-http-kernel](../xtr-http-kernel)'s
`StarletteHttpFactory.create_response()`.

## The classes

| Class | Implements |
| --- | --- |
| `Request` | `RequestInterface` |
| `ServerRequest` | `ServerRequestInterface` |
| `Response` | `ResponseInterface` |
| `Stream` | `StreamInterface` |
| `Uri` | `UriInterface` |
| `UploadedFile` | `UploadedFileInterface` |
| `HttpFactory` | all six factory interfaces |

Each one names its interface as its last base class, so `isinstance` and a container
registration both work without a plugin registry in between.

### The rules that hold across all of them

- **Messages are immutable.** Every `with_*` method leaves the instance it was called on as it
  was and returns one carrying the change — and hands *the same instance* back when the change
  would change nothing, so a chain of `with_*` calls costs nothing where it does nothing.
- **A stream is the one thing that is not.** Reading, writing and seeking move its cursor in
  place.
- **The payload is bytes throughout.** `bytes(stream)` rewinds and reads the whole of a body and
  never raises; `str(stream)` is *not* the body — there is no encoding to guess at.
- **Header names are matched without regard to case** and reported in the case they were first
  given in. A header the message does not carry reads as an empty list and an empty line, never
  as an error. Names and values are checked against the grammar, so no value can inject a
  header of its own.
- **Nothing you are handed can change the message.** `get_headers()`, `get_header()`,
  `get_query_params()` and the rest hand back a fresh mapping or list every time.
- **A body is opened only when it is asked for.** A message built with no body opens nothing
  until `get_body()` is called.

### Streams

`Stream.create()` takes the payload in any of the three shapes a body arrives in:

```python
from io import BytesIO

from xtr_http_message import Stream

Stream.create(b"hello")  # bytes, held in memory
Stream.create(BytesIO(b"hello"))  # an open binary file object, taken over
Stream.create(Stream.create(b"hello"))  # already a stream — handed straight back
```

A stream takes the file object over: closing the stream closes it. It does *not* close it when
the stream itself is collected, so a file object you still hold is yours to close.

`get_metadata()` reports three entries — `mode`, `seekable` and `uri`, the last being the path
the file was opened on when it has one.

### URIs

A URI is a value, read as RFC 3986 defines a URI reference — the splitting is `uritools`' work.
Components arrive encoded or not, as you have them, and come back encoded exactly once:

```python
from xtr_http_message import Uri

assert str(Uri().with_path("/pa th")) == "/pa%20th"
assert Uri("/p%61th").get_path() == "/p%61th"
```

The standard port of the scheme is dropped, since it says nothing the scheme does not:
`Uri("https://example.com:443").get_port()` is `None`. Change the scheme and the port is weighed
again.

Nothing is trimmed and no character is dropped: a blank, a tab or a control character in a path,
a query string or a fragment comes back as its per cent escape, so the URI you asked about is the
URI you get an answer about. What *is* refused — with `InvalidArgumentError` naming the whole
string, rather than any of it corrected — is a URI whose authority says something that is not an
authority:

- a host that is neither an IPv6 address in two brackets nor a registered name of unreserved
  characters, per cent escapes and sub-delimiters — `http://exa mple.com`, `http://[::1`,
  `http://h%2`, or a name written in another script, which reaches a host in its `xn--` form —
  including a scoped-address zone identifier between the brackets, which that grammar has no room
  for: `http://[fe80::1%eth0]` (RFC 3986 §3.2.2);
- a port outside the sixteen bits a TCP or UDP port is assigned from — `http://h:65536`
  (RFC 3986 §3.2.3);
- a port with no host to hang off, which no authority could be written from — `//:80`,
  `foo://:8080` (RFC 3986 §3.2);
- an `http` or `https` URI naming an authority with no host in it — `http://`, `http://:80/`
  (RFC 9110 §4.2.1 and §4.2.2).

`with_host` reads a host by those same rules — the `Host` header of a request is written straight
off that component, so nothing a parse would refuse may reach it by the back door either.

Everything else is read rather than refused, which is not the same as being a URI reference. A
scheme opens with a letter, so `0:foo` is a relative reference whose path is `0:foo`; a scheme
other than `http` or `https` may name an empty authority, so `file:///etc/hosts` has no host and
the path `/etc/hosts`. A string whose front is no scheme at all is read as a path and comes back
per cent-encoded, and the result may still be no URI reference: RFC 3986 §4.2 leaves a colon out
of the first segment of a relative-path reference, so `0:0` and `ht tp://h/` come back as paths
that would read as a scheme to whoever resolved them. Write `./` in front of such a path, or give
the reference a scheme.

```python
from xtr_http_message import Uri

assert Uri("http://h/a\nb").get_path() == "/a%0Ab"
assert (Uri("0:foo").get_scheme(), Uri("0:foo").get_path()) == ("", "0:foo")

local = Uri("file:///etc/hosts")
assert (local.get_scheme(), local.get_host(), local.get_path()) == ("file", "", "/etc/hosts")
```

### Uploaded files

Two kinds arrive. One is already a stream and comes back as that same stream. The other is a
path on disk, opened only when the file is read — so a request carrying twenty files nobody
looks at opens none of them. `move_to()` is what consumes a file: a path is moved, a stream is
copied a mebibyte at a time, and a second move is refused.

## Use in an application

- **Install** — `uv add xtr-http-message`.
- **Recipe** — none. There is nothing to write into an application: no bundle to list, no
  configuration file, no environment variable, no path to ignore.
- **Activate** — nothing to activate. These are classes, not a service: build one where you need
  one, or take `HttpFactory` as a dependency and let it build them.
- **Brings along** — `xtr-http-message-contracts`, `typing-extensions` and `uritools`. No web
  framework, no container, no I/O until a stream is read.
- **Configure** — nothing to configure.
- **Environment** — nothing to set.
- **Ignore** — nothing to ignore.
- **Remove** — `uv remove xtr-http-message`.
- **Check** — `python -c "from xtr_http_message import HttpFactory; print(HttpFactory().create_response(404).get_reason_phrase())"`
  prints `Not Found`.

Registering these classes on a container, and bridging a message to the web framework the
application runs on — building one from the call in flight, returning one from a route — belongs
with that framework's integration. For a FastAPI application that is
[xtr-http-kernel](../xtr-http-kernel); read its *Use in an application* section for what it
registers and what it asks of a route.

One thing it asks is worth repeating here: **do not build a `Response` or an `HttpFactory` from
this package in code that is serving a request.** A served response comes from the injected
`ResponseFactoryInterface`, or is the injected `ResponseInterface`, and goes out as it is — see
[Responses in a served application](#responses-in-a-served-application).

## Errors

| Error | Is also | Raised when |
| --- | --- | --- |
| `HttpMessageError` | — | Never raised itself; the one base class the other three share |
| `InvalidArgumentError` | `ValueError` | An argument cannot be what it is being used as — a malformed header name, an out-of-range port, a status code that is not one, a URI that cannot be read |
| `StreamError` | `RuntimeError` | A stream cannot do what is being asked of it — detached, not seekable, not readable, a file that will not open |
| `UploadedFileError` | `RuntimeError` | An uploaded file is unusable — the upload failed, or the file has already been moved |

The contract names `ValueError` and `RuntimeError`, so code written against the interfaces
catches the builtin and never names this package. Code that chose this implementation can catch
`HttpMessageError` instead and get only its failures.

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-http-message`; run the commands below from there. The `python-xtr-http-message`
repository is a read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync
uv run ruff check . && uv run ruff format --check .
uv run basedpyright
uv run ty check
uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
